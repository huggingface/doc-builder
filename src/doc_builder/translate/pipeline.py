"""
The middle of the pipeline: build the prompt, take a page apart, put it back together, and
run the model.

Everything here except `translate_segments` is ordinary text handling with no GPU involved,
which is why the tests can cover it in under a second on a laptop.

`torch` and `transformers` are imported inside `translate_segments` rather than at the top
of the file. That way a night where nothing has changed never loads them at all, and the
rest of this file can be imported anywhere.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import yaml

from . import validate
from .cache import segment_key, sha256_text
from .segment import is_translatable, join_blocks, mask, restore, split_blocks

# Change this to redo every translation from scratch. It is part of each paragraph's ID, so
# editing it throws the whole cache away -- about $2.50-10 of GPU time for transformers.
PROMPT_VERSION = "v1"

LANGUAGE_NAMES = {"ja": "Japanese"}

# How attention is computed. Continuous batching needs a paged backend, and the `paged|`
# prefix asks for one.
#
# sdpa is the default because it is built into PyTorch and always works. FlashAttention is
# faster, but it needs either the compiled flash-attn package or a prebuilt kernel from the
# Hub that matches the exact torch and CUDA version in the image -- and on a job image running
# torch 2.13/CUDA 13, kernels-community/flash-attn2 published nothing newer than torch 2.12,
# so loading the model failed outright. For a job that runs unattended overnight, a crash
# costs a whole day of translations while slower decoding costs minutes.
#
# Override with --attn-implementation when you know the image has FlashAttention available.
DEFAULT_ATTENTION = "paged|sdpa"

# On purpose, this does not name a particular library. The prompt is part of each
# paragraph's ID, so keeping it generic means the same boilerplate sentence translated for
# one library can be reused for another instead of being paid for twice.
SYSTEM_PROMPT = """You are translating technical documentation for a Hugging Face \
library from English into {language}.

Rules:
- Translate only the prose. Preserve the Markdown structure exactly.
- Tokens like {ph_open}0{ph_close} are opaque placeholders for code, tags and URLs. \
Reproduce every placeholder exactly once, unchanged, in a natural position. Never \
translate, renumber, drop or duplicate them.
- Keep heading levels (`#`, `##`) exactly as they are.
- Output only the translation. No preamble, no explanation, no code fences.{glossary}"""

GLOSSARY_HEADER = "\n- Use these renderings exactly:"


def glossary_path(language):
    """Where the glossary for this language lives inside the installed package.

    Same approach `mock_imports` uses to find its own data files.
    """
    return Path(__file__).parent.parent / "glossaries" / f"{language}.yml"


def load_glossary(path):
    """Read a glossary file. Returns an empty one if there is no file there."""
    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return {}


def glossary_sha(glossary):
    """A short fingerprint of the glossary, so editing it re-translates the affected text."""
    return sha256_text(yaml.safe_dump(glossary or {}, sort_keys=True, allow_unicode=True))


def glossary_for_segment(segment_text, glossary):
    """Pick out just the glossary terms that actually appear in this paragraph.

    We could send the whole glossary every time, but there are around 14,000 paragraphs and
    the model cannot reuse any of that work between them, so every unused line would be paid
    for 14,000 times over.
    """
    if not glossary:
        return {}
    low = segment_text.lower()
    return {term: rendering for term, lowered, rendering in _pins(glossary) if lowered in low}


@lru_cache(maxsize=8)
def _pins_cached(items):
    return tuple((term, term.lower(), rendering) for term, rendering in items)


def _pins(glossary):
    """The glossary terms with their lowercase form worked out once, instead of per paragraph."""
    return _pins_cached(tuple(sorted((glossary.get("pin") or {}).items())))


def build_prompt(segment_text, language, glossary):
    """Build the instructions and the paragraph into a chat message for the model."""
    terms = glossary_for_segment(segment_text, glossary)
    if terms:
        lines = "".join(f"\n  - {t} -> {r}" for t, r in sorted(terms.items()))
        glossary_block = GLOSSARY_HEADER + lines
    else:
        glossary_block = ""

    system = SYSTEM_PROMPT.format(
        language=LANGUAGE_NAMES.get(language, language),
        ph_open="⟦",
        ph_close="⟧",
        glossary=glossary_block,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": segment_text},
    ]


# -- page pipeline (pure, no GPU) ------------------------------------------------


class Unit(NamedTuple):
    """One paragraph to translate, with its surrounding blank space kept to one side.

    Trimming the blank space before working out the ID matters more than it sounds. The last
    chunk on a page keeps a trailing newline, so without trimming, the same sentence would
    get two different IDs and be translated twice. The docs repeat a lot of boilerplate --
    "The abstract from the paper is the following:" appears across 513 model pages -- and
    trimming means all of those share one translation. We keep the spacing so the page can be
    rebuilt exactly as it was.
    """

    key: str
    text: str
    lead: str
    trail: str


class PagePlan:
    """A page broken into pieces, ready to translate.

    `parts` is the whole page in chunks. `units` picks out just the chunks with prose in
    them and notes each one's ID. Everything else passes straight through untouched.
    """

    def __init__(self, page, source, language, model_id, gloss_sha):
        self.page = page
        self.source = source
        self.masked, self.placeholders = mask(source)
        self.parts = split_blocks(self.masked)
        self.units = {}
        for i, part in enumerate(self.parts):
            if i % 2 != 0 or not is_translatable(part):
                continue
            core = part.strip()
            lead = part[: len(part) - len(part.lstrip())]
            trail = part[len(part.rstrip()) :]
            key = segment_key(core, model_id, PROMPT_VERSION, gloss_sha, language)
            self.units[i] = Unit(key, core, lead, trail)

    @property
    def segments(self):
        """The paragraphs to send to the model. Repeats collapse into one."""
        return {u.key: u.text for u in self.units.values()}


def assemble_page(plan, translations):
    """Put a page back together from its translated paragraphs.

    If a paragraph is missing a translation, its English is left in place. That is on
    purpose: a page that is mostly translated beats no page at all, and it still has to pass
    the checks before anyone sees it.
    """
    parts = list(plan.parts)
    for index, unit in plan.units.items():
        if unit.key in translations:
            parts[index] = f"{unit.lead}{translations[unit.key]}{unit.trail}"
    masked_translation = join_blocks(parts)
    return masked_translation, restore(masked_translation, plan.placeholders)


def validate_plan(plan, masked_translation, glossary=None, restored=None):
    return validate.validate_page(
        plan.page,
        plan.masked,
        masked_translation,
        glossary,
        source=plan.source,
        restored=restored,
    )


# -- disclosure -----------------------------------------------------------------

DISCLOSURE = {
    "ja": (
        "> [!TIP]\n"
        "> このページは機械翻訳されています。原文は[英語版]({en_url})を参照してください。\n"
        "> 翻訳の問題は[こちら]({issue_url})から報告できます。\n"
    )
}

# The library name is filled in rather than written in. This command works on any library, so
# hardcoding "transformers" would put a link to the wrong docs site on every page of every
# other library, and send its bug reports to the wrong repo.
EN_DOCS_URL = "https://huggingface.co/docs/{package}/en/{slug}"
DISCLOSURE_FALLBACK = (
    "> [!TIP]\n"
    "> This page was machine-translated. See the [English original]({en_url}).\n"
    "> Report translation problems [here]({issue_url}).\n"
)

ISSUE_URL = "https://github.com/huggingface/{package}/issues/new?labels=documentation"
LICENSE_HEADER_RE = re.compile(r"\A(<!--.*?-->\n)", re.DOTALL)


def add_disclosure(page_text, page, language, package):
    """Add the "this was machine-translated" notice, just below the licence header.

    This is us being upfront, not a substitute for review. Readers should know that nobody
    checked this page.
    """
    # If we have no notice written for this language, use the English one rather than adding
    # nothing at all. Quietly publishing a machine translation with no warning on it is the
    # exact thing this function exists to stop.
    banner = DISCLOSURE.get(language, DISCLOSURE_FALLBACK)
    slug = page[:-3] if page.endswith(".md") else page
    banner = banner.format(
        en_url=EN_DOCS_URL.format(package=package, slug=slug),
        issue_url=ISSUE_URL.format(package=package),
    )
    match = LICENSE_HEADER_RE.match(page_text)
    if match:
        return f"{match.group(1)}\n{banner}\n{page_text[match.end() :].lstrip(chr(10))}"
    return f"{banner}\n{page_text}"


# -- toctree --------------------------------------------------------------------


def toctree_dicts(node):
    """Walk every entry in the sidebar file, top to bottom.

    Reading and writing both go through here, so if the sidebar format ever grows a new kind
    of entry, this is the only place that needs to learn about it.
    """
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from toctree_dicts(value)
    elif isinstance(node, list):
        for item in node:
            yield from toctree_dicts(item)


def toctree_values(node, field):
    """Collect one field from every sidebar entry -- the titles, or the page names."""
    return [d[field] for d in toctree_dicts(node) if isinstance(d.get(field), str)]


def toctree_titles(node):
    return toctree_values(node, "title")


def prune_toctree(node, keep_locals):
    """Cut the sidebar down to just the pages we are translating.

    This is for test runs on a handful of pages. The sidebar lists every page in the docs, so
    if we copied it over unchanged next to three translated pages, doc-builder would refuse to
    build and tell us to remove the missing entries. It also stops a three-page test run from
    translating all 756 sidebar titles.

    Sidebar entries come in two shapes: a page, or a group of pages. A group is kept only if
    something inside it survived, so we do not leave empty headings behind. Returns None if
    nothing is left at all.
    """
    if isinstance(node, list):
        kept = [p for p in (prune_toctree(item, keep_locals) for item in node) if p is not None]
        return kept or None
    if isinstance(node, dict):
        if "local" in node:
            return dict(node) if node["local"] in keep_locals else None
        if "sections" in node:
            sections = prune_toctree(node["sections"], keep_locals)
            if sections is None:
                return None
            return {**node, "sections": sections}
    return node


def apply_toctree_titles(node, translations):
    """Swap the sidebar titles for their translations."""
    for d in toctree_dicts(node):
        if isinstance(d.get("title"), str):
            d["title"] = translations.get(d["title"], d["title"])
    return node


# -- model ----------------------------------------------------------------------


def build_requests(segments, tokenizer, language, glossary, max_new_token_ratio=2.5):
    """Turn each paragraph into something the model can read, plus a length limit.

    The length limit is worked out from the paragraph alone, not the whole prompt. The
    instructions are about 150 tokens and a typical paragraph is only about 16, so measuring
    the whole thing would hand a one-line heading roughly six times the room it needs.
    """
    requests = []
    for key, text in segments.items():
        prompt = tokenizer.apply_chat_template(
            build_prompt(text, language, glossary),
            tokenize=True,
            add_generation_prompt=True,
        )
        # Japanese output runs longer in tokens than English input, so one global cap
        # would either truncate long blocks or waste KV budget.
        content_tokens = len(tokenizer.encode(text, add_special_tokens=False))
        budget = int(content_tokens * max_new_token_ratio) + 48
        requests.append((key, prompt, budget))
    return requests


def translate_segments(
    segments, language, glossary, model_id, max_new_token_ratio=2.5, attn_implementation=DEFAULT_ATTENTION
):
    """Translate a batch of paragraphs on the GPU.

    Paragraphs range from a few words to a couple of thousand, and continuous batching is
    built for exactly that: as each one finishes, the next joins in, instead of everything
    waiting for the longest one in the group.

    We drive it through the manager rather than `generate_batch` because the manager lets us
    label each request ourselves. Labelling each one with its cache ID means results file
    themselves away as they arrive, and it does not matter what order they come back in.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from transformers.generation import ContinuousBatchingConfig, GenerationConfig
    from transformers.generation.continuous_batching.utils import WorkloadHints

    if not segments:
        return {}, []

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        attn_implementation=attn_implementation,
        device_map="cuda",
        dtype=torch.bfloat16,
    )

    requests = build_requests(segments, tokenizer, language, glossary, max_new_token_ratio)
    max_prompt = max(len(p) for _, p, _ in requests)
    max_generated = max(b for _, _, b in requests)

    cb_config = ContinuousBatchingConfig(
        max_batch_tokens=16384,
        use_cuda_graph=True,
        # Compiling the model is worth it on a long run but not a short one, where the
        # setup time would be most of the job.
        default_compile_level=1 if len(requests) > 500 else 0,
        max_requests_per_batch=256,  # keeps memory use in check on big batches
    )
    generation_config = GenerationConfig(
        max_new_tokens=max_generated,
        # Always pick the most likely word rather than sampling, so running the same
        # paragraph twice gives the same answer. Otherwise a cached translation and a fresh
        # one could differ, with no way to tell which we were looking at.
        do_sample=False,
        eos_token_id=tokenizer.eos_token_id,
    )
    # Telling it roughly what to expect lets it set aside the right amount of memory up
    # front, instead of guessing.
    hints = WorkloadHints(
        max_prompt_length=max_prompt,
        max_generated_length=max_generated,
        num_requests=len(requests),
    )

    translations, failures = {}, []
    with model.continuous_batching_context_manager(
        generation_config=generation_config,
        continuous_batching_config=cb_config,
        workload_hints=hints,
    ) as manager:
        for key, prompt, budget in requests:
            manager.add_request(input_ids=prompt, request_id=key, max_new_tokens=budget)

        # Stop once we have heard back about every request. We cannot just loop until the
        # results run out: the loop keeps going while the background worker is alive, and
        # that worker is only shut down when we leave this block -- so waiting for it to
        # finish from in here would hang forever.
        for result in manager:
            if result.error or not result.is_finished():
                failures.append((result.request_id, result.error or str(result.status)))
            else:
                translations[result.request_id] = tokenizer.decode(
                    result.generated_tokens, skip_special_tokens=True
                ).strip()
            if len(translations) + len(failures) >= len(requests):
                break

    missing = set(segments) - set(translations) - {k for k, _ in failures}
    for key in missing:
        failures.append((key, "no result returned"))
    return translations, failures
