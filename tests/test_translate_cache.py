import pytest

from doc_builder.translate import pipeline
from tests.translate_harness import config, files, generate


def execute(source, cache=None, cfg=None, fn=generate):
    return pipeline.translate(source, cfg or config(), cache or {}, fn)


def no_gpu(*args, **kwargs):
    pytest.fail("Warm cache initialized generation")


def test_cold_then_warm_includes_sidebar():
    source = files()
    output, cache, failures = execute(source)
    assert not failures
    assert len(cache) == 3
    again, next_cache, failures = execute(source, cache, fn=no_gpu)
    assert not failures and again == output and next_cache == cache
    assert output["image.svg"] == source["image.svg"]


@pytest.mark.parametrize("damage", ["structure", "unicode"])
def test_cache_validation_accepts_only_current_complete_pages_without_translation(monkeypatch, damage):
    source, cfg = files(), config()
    output, cache, _ = execute(source, cfg=cfg)
    key = pipeline.cache_key("index.md", source["index.md"], cfg)
    cache[key] = "# Broken\n" if damage == "structure" else cache[key].replace("翻訳です。", "翻訳です。\ud800")
    cache["obsolete-source-key"] = "Old translation"
    monkeypatch.setattr(pipeline, "translate", no_gpu)
    monkeypatch.setattr(pipeline, "load_model", no_gpu)

    accepted, valid = pipeline.load_valid_cache(source, cfg, cache)

    assert accepted == {name: output[name] for name in ("guide.mdx", "_toctree.yml")}
    assert len(valid) == 2 and "obsolete-source-key" not in valid


@pytest.mark.parametrize(
    "edit",
    [
        lambda s: s.replace(b"Read the guide.", b"Read another guide."),
        lambda s: s + b"\n```python\ncode = 2\n```\n",
        lambda s: s + b"\n[More guidance](https://example.com/changed)\n",
        lambda s: s + b'\n<img src="new.svg"/>\n',
        lambda s: s.replace(b"Read the guide.\n", b""),
    ],
)
def test_whole_page_key_includes_every_source_byte(edit):
    source = files()
    _, cache, _ = execute(source)
    source["index.md"] = edit(source["index.md"])
    calls = []

    def record(units, cfg, retry=False):
        calls.extend(u["text"] for u in units)
        return generate(units, cfg, retry)

    _, changed, failures = execute(source, cache, fn=record)
    assert not failures and calls
    assert len(set(cache) & set(changed)) == 2


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.update(version=c["version"] + 1),
        lambda c: c.update(model_revision="b" * 40),
        lambda c: c.update(tokenizer_revision="b" * 40),
        lambda c: c["glossary"]["keep"].append("Transformers"),
        lambda c: c.update(output=c["output"] + 1),
    ],
)
def test_configuration_invalidates_cache(mutate):
    source, cfg = files(), config()
    _, cache, _ = execute(source, cfg=cfg)
    mutate(cfg)
    _, changed, failures = execute(source, cache, cfg)
    assert not failures and not set(cache) & set(changed)


@pytest.mark.parametrize(
    "poison", ["", "   ", 4, None, "# Introduction\n\nRead the guide.\n", "# 翻訳\n", "# 翻訳\n\n¤999¤\n"]
)
def test_corrupt_cache_values_are_misses(poison):
    source = files()
    output, cache, _ = execute(source)
    poisoned = dict.fromkeys(cache, poison)
    rebuilt, _, failures = execute(source, poisoned)
    assert not failures and rebuilt == output


def test_deleted_file_and_reordered_paragraphs_have_fresh_output():
    source = files()
    source["index.md"] += b"\nA second paragraph.\n"
    _, cache, _ = execute(source)
    del source["guide.mdx"]
    source["_toctree.yml"] = b"- local: index\n  title: Introduction\n"
    source["index.md"] = b"# Introduction\n\nA second paragraph.\n\nRead the guide.\n"
    output, candidate, failures = execute(source, cache)
    assert not failures and "guide.mdx" not in output
    assert len(candidate) == 2


def test_invalid_sidebar_cache_paths_are_recomputed():
    source = files()
    _, cache, _ = execute(source)
    for key, text in cache.items():
        if "local:" in text:
            cache[key] = text.replace("index", "ghost")
    output, _, failures = execute(source, cache)
    assert not failures and b"ghost" not in output["_toctree.yml"]
