# Copyright 2026 The HuggingFace Team. Licensed under the Apache License, Version 2.0.
"""Translate complete source snapshots; cache complete, validated pages."""

import hashlib
import json
import re
import subprocess
from functools import cache as memoize
from pathlib import Path

import yaml

from .segment import PLACEHOLDER_RE, accept_unit, extract_pages, render_page, required, validate_pages

# Uniform KV dimensions are required by the pinned continuous-batching cache.
MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"
# The runtime pins the public generate_batch implementation inspected for result ordering.
TRANSFORMERS_REVISION = "58a94493a64f74d04279a3a617297dfe355b0b89"
LANGUAGES = {"ja": "Japanese"}
SETTINGS = {"version": 6, "attention": "paged|sdpa", "context": 16384, "output": 4096, "group": 64}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def configuration(language, model_revision):
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language {language!r}; configure it in LANGUAGES first")
    if not re.fullmatch(r"[a-f0-9]{40}", model_revision):
        raise ValueError("Model revision must be a full commit SHA")
    glossary = yaml.safe_load((Path(__file__).parents[1] / "glossaries" / f"{language}.yml").read_text())
    from ..utils import locate_kit_folder

    kit_hash = hashlib.sha256((locate_kit_folder() / "package-lock.json").read_bytes()).hexdigest()
    return {
        "kit_hash": kit_hash,
        **SETTINGS,
        "language": language,
        "model": MODEL,
        "model_revision": model_revision,
        "tokenizer_revision": model_revision,
        "glossary": glossary,
        "transformers": TRANSFORMERS_REVISION,
    }


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, encoding="utf-8").strip()


def sidebar_items(node):
    if isinstance(node, list):
        for value in node:
            yield from sidebar_items(value)
    elif isinstance(node, dict):
        yield node
        for value in node.values():
            yield from sidebar_items(value)


def check_sidebar(files):
    pages = {str(Path(name).with_suffix("")) for name in files if Path(name).suffix in {".md", ".mdx"}}
    if not pages or "_toctree.yml" not in files:
        raise ValueError("Source needs Markdown pages and _toctree.yml")
    tree = yaml.safe_load(files["_toctree.yml"])
    if not isinstance(tree, list) or not tree:
        raise ValueError("Sidebar must be a nonempty list")
    for item in sidebar_items(tree):
        if "local" in item:
            local = item["local"]
            if not isinstance(local, str) or sum(local + ext in files for ext in (".md", ".mdx")) != 1:
                raise ValueError(f"Sidebar page does not resolve uniquely: {local!r}")
        if "title" in item and (not isinstance(item["title"], str) or not item["title"].strip()):
            raise ValueError("Sidebar titles must be nonempty strings")
    if not any("title" in item for item in sidebar_items(tree)):
        raise ValueError("Sidebar needs at least one title")
    return tree


def inventory(repo, source_revision, pages=None):
    """Read every tracked source file, including pages absent from the sidebar."""
    repo = Path(repo).resolve()
    if git(repo, "rev-parse", "HEAD") != source_revision:
        raise ValueError("Source checkout does not match the requested revision")
    if git(repo, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("Source checkout has tracked changes; use a clean checkout")
    root = repo / "docs/source/en"
    tracked = git(repo, "ls-tree", "-r", "--name-only", "-z", source_revision, "--", "docs/source/en")
    files = {}
    for name in tracked.split("\0"):
        if not name:
            continue
        path = repo / name
        if not path.resolve(strict=True).is_relative_to(repo):
            raise ValueError(f"Source symlink escapes the repository: {name}")
        files[path.relative_to(root).as_posix()] = path.read_bytes()
    tree = check_sidebar(files)
    if pages is not None:
        selected = set(pages)
        if not selected or any(name not in files or Path(name).suffix not in {".md", ".mdx"} for name in selected):
            raise ValueError("Preview needs at least one existing .md or .mdx page")
        locals_ = {str(Path(name).with_suffix("")) for name in selected}

        def prune(items):
            result = []
            for item in items:
                item = dict(item)
                if "local" in item and item["local"] not in locals_:
                    continue
                if "sections" in item:
                    item["sections"] = prune(item["sections"])
                    if not item["sections"]:
                        continue
                result.append(item)
            return result

        tree = prune(tree)
        if not tree:
            tree = [{"local": str(Path(name).with_suffix("")), "title": Path(name).stem} for name in sorted(selected)]
        files = {
            name: value
            for name, value in files.items()
            if Path(name).suffix not in {".md", ".mdx"} or name in selected
        }
        files["_toctree.yml"] = yaml.safe_dump(tree, allow_unicode=True, sort_keys=False).encode()
    return files, tree


def pins(text, config):
    return {
        term: target
        for term, target in (config["glossary"].get("pin") or {}).items()
        if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.I)
    }


def accept(unit, text, config):
    text = accept_unit(unit, text)
    for term, target in pins(unit["text"], config).items():
        if target not in text:
            raise ValueError(f"Translation needs glossary rendering {term!r}: {target}")
    return text


def xml_tags(unit):
    """Give the model explicit pairs while retaining internal marker identities."""
    pairs = {t["pair"]: i for i, t in enumerate(unit["tokens"]) if t["kind"] == "open"}
    return [
        f"<g{i}>" if t["kind"] == "open" else f"</g{pairs[t['pair']]}>" if t["kind"] == "close" else f"<ph{i}/>"
        for i, t in enumerate(unit["tokens"])
    ]


def prompt(unit, config, retry=False):
    text = (
        f"Translate English into {LANGUAGES[config['language']]}. Return only the translation, without explanations."
    )
    if "¤" in unit["text"]:
        text += " Preserve every XML tag exactly, including paired opening and closing tags. Do not add any tags. Translate only the prose."
        if retry:
            text += " Check that all opening, closing, and self-closing tags are present before answering."
    terms = pins(unit["text"], config)
    if terms:
        text += " Required translations: " + json.dumps(terms, ensure_ascii=False)
    return text


@memoize
def load_model(model_id, revision, attention):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision, device_map="cuda", dtype=torch.bfloat16, attn_implementation=attention
    )
    return tokenizer, model


def split_unit(unit, tokenize, limit):
    """Split only between complete inline elements; never truncate a prompt."""
    if len(tokenize(unit)) <= limit:
        return [unit]
    stack, boundaries = [], []
    for match in re.finditer(r"¤(\d+)¤|\s+", unit["text"]):
        if match[1] is not None:
            token = unit["tokens"][int(match[1])]
            if token["kind"] == "open":
                stack.append(token["pair"])
            elif token["kind"] == "close":
                stack.pop()
        elif not stack and match.start() > 0 and match.end() < len(unit["text"]):
            boundaries.append(match.end())
    if not boundaries:
        raise ValueError("Prose unit exceeds the context budget and has no safe split")
    middle = min(boundaries, key=lambda offset: abs(offset - len(unit["text"]) / 2))
    return split_unit({**unit, "text": unit["text"][:middle]}, tokenize, limit) + split_unit(
        {**unit, "text": unit["text"][middle:]}, tokenize, limit
    )


def generate(units, config, retry=False):
    """One public continuous-batching call per bounded group; model loads once."""
    from transformers import GenerationConfig
    from transformers.generation import ContinuousBatchingConfig

    tokenizer, model = load_model(config["model"], config["model_revision"], config["attention"])
    budget = config["output"] * (2 if retry else 1)

    def tokenize(unit):
        tags = xml_tags(unit)
        source = PLACEHOLDER_RE.sub(lambda m: tags[int(m[1])], unit["text"])
        return tokenizer.apply_chat_template(
            [{"role": "system", "content": prompt(unit, config, retry)}, {"role": "user", "content": source}],
            tokenize=True,
            add_generation_prompt=True,
            return_dict=False,
            enable_thinking=False,
        )

    chunks = [split_unit(unit, tokenize, config["context"] - budget) for unit in units]
    flat = [chunk for group in chunks for chunk in group]
    inputs = [tokenize(chunk) for chunk in flat]
    decoded = []
    for offset in range(0, len(inputs), config["group"]):
        group = inputs[offset : offset + config["group"]]
        outputs = model.generate_batch(
            group,
            generation_config=GenerationConfig(
                do_sample=False, max_new_tokens=budget, eos_token_id=model.generation_config.eos_token_id
            ),
            continuous_batching_config=ContinuousBatchingConfig(
                use_cuda_graph=False,
                default_compile_level=0,
                max_memory_percent=0.8,
                max_batch_tokens=16384,
                max_requests_per_batch=config["group"],
            ),
        )
        values = list(outputs.values())
        eos = model.generation_config.eos_token_id
        eos = {eos} if isinstance(eos, int) else set(eos or [tokenizer.eos_token_id])
        if len(values) != len(group) or any(
            o.error
            or not o.is_finished()
            or not o.generated_tokens
            or o.generated_tokens[-1] not in eos
            or o.prompt_ids != ids
            for o, ids in zip(values, group, strict=True)
        ):
            raise ValueError("Continuous batching returned missing, failed, truncated, or misordered results")
        for unit, output in zip(flat[offset : offset + len(group)], values, strict=True):
            text = tokenizer.decode(output.generated_tokens, skip_special_tokens=True)
            for i, tag in enumerate(xml_tags(unit)):
                text = text.replace(tag, f"¤{i}¤")
            decoded.append(text)
    result, cursor = [], 0
    for group in chunks:
        result.append(" ".join(decoded[cursor : cursor + len(group)]))
        cursor += len(group)
    return result


def validate_cached(plans, values, config):
    translated = validate_pages(plans, values, config["glossary"].get("keep") or [])
    for plan, result in zip(plans, translated, strict=True):
        for before, after in zip(plan["units"], result["units"], strict=True):
            for target in pins(before["text"], config).values():
                if target not in after["text"]:
                    raise ValueError("Cached glossary mismatch")


def translate(files, tree, config, cache, generate_fn=generate):
    """Return accepted source, complete-page cache candidate, and explicit failures."""
    tree = yaml.safe_load(files["_toctree.yml"])
    names = sorted(name for name in files if Path(name).suffix in {".md", ".mdx"})
    sources = [files[name].decode("utf-8") for name in names]
    keep = config["glossary"].get("keep") or []
    page_plans = extract_pages(sources, keep, normalize=True)
    title_items = [item for item in sidebar_items(tree) if "title" in item]
    title_plans = extract_pages([item["title"] for item in title_items], keep)
    documents = {name: [plan] for name, plan in zip(names, page_plans, strict=True)}
    documents["_toctree.yml"] = title_plans
    keys = {
        name: digest(
            {"package": "transformers", "path": name, "source": files[name].decode("utf-8"), "config": config}
        )
        for name in documents
    }
    candidate, output, pending, errors = {}, dict(files), {}, {}
    for name, plans in documents.items():
        value = cache.get(keys[name])
        try:
            if not isinstance(value, str):
                raise ValueError("Cache miss")
            values = [value]
            if name == "_toctree.yml":
                cached_tree = check_sidebar({**files, name: value.encode()})
                cached_items = [item for item in sidebar_items(cached_tree) if "title" in item]
                values = [item["title"] for item in cached_items]
                # Compare every YAML value except the titles being translated.
                for item in cached_items:
                    item["title"] = ""
                original_tree = yaml.safe_load(files[name])
                for item in sidebar_items(original_tree):
                    if "title" in item:
                        item["title"] = ""
                if original_tree != cached_tree:
                    raise ValueError("Cached sidebar structure mismatch")
            validate_cached(plans, values, config)
            candidate[keys[name]], output[name] = value, value.encode()
        except (ValueError, TypeError, yaml.YAMLError):
            pending[name] = plans
    for attempt in range(2):
        if not pending:
            break
        print(f"Translating {len(pending)} documents (attempt {attempt + 1}/2)", flush=True)
        requests = [
            (name, pi, ui, unit)
            for name, plans in pending.items()
            for pi, plan in enumerate(plans)
            for ui, unit in enumerate(plan["units"])
            if required(unit)
        ]
        answers = {}
        for offset in range(0, len(requests), config["group"]):
            group = requests[offset : offset + config["group"]]
            print(f"Generating units {offset + 1}-{offset + len(group)} of {len(requests)}", flush=True)
            try:
                responses = generate_fn([r[3] for r in group], config, retry=bool(attempt))
                if len(responses) != len(group):
                    raise ValueError("Incomplete generation group")
                for (name, pi, ui, unit), response in zip(group, responses, strict=True):
                    try:
                        answers[name, pi, ui] = accept(unit, response, config)
                    except ValueError as exc:
                        errors[name] = (
                            f"Unit {pi + 1}.{ui + 1}: {exc}; "
                            f"source={unit['text'][:300]!r}; response={str(response)[:300]!r}"
                        )
                        print(f"Rejected {name}: {errors[name]}", flush=True)
            except (ValueError, RuntimeError) as exc:
                for name, *_ in group:
                    errors[name] = str(exc)
        for name, plans in list(pending.items()):
            try:
                values = [
                    render_page(
                        plan,
                        [answers[name, pi, ui] if required(u) else u["text"] for ui, u in enumerate(plan["units"])],
                    )
                    for pi, plan in enumerate(plans)
                ]
                validate_cached(plans, values, config)
                value = values[0]
                if name == "_toctree.yml":
                    for item, title in zip(title_items, values, strict=True):
                        item["title"] = title
                    value = yaml.safe_dump(tree, allow_unicode=True, sort_keys=False)
                candidate[keys[name]], output[name] = value, value.encode()
                del pending[name]
                print(f"Accepted {name}", flush=True)
            except (KeyError, ValueError) as exc:
                errors.setdefault(name, str(exc))
    failures = [f"{name}: {errors.get(name, 'incomplete translation')}" for name in pending]
    if not failures:
        check_sidebar(output)
    return output, candidate, failures
