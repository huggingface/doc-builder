"""Cache tests, all on a local-directory backend -- no network."""

from doc_builder.translate import cache

MODEL = "google/gemma-4-26B-A4B-it"
PROMPT = "v1"
GLOSSARY = "abc123"


def key_for(text, **over):
    args = {
        "masked_text": text,
        "model_id": MODEL,
        "prompt_version": PROMPT,
        "glossary_sha": GLOSSARY,
        "language": "ja",
    }
    args.update(over)
    return cache.segment_key(**args)


def test_cold_miss_then_warm_hit(tmp_path):
    c = cache.SegmentCache(tmp_path)
    k = key_for("The tokenizer converts text.")

    assert c.load_index() == set()
    assert c.get(k) is None

    assert c.put(k, "トークナイザーはテキストを変換します。")
    assert c.save_index() == 1

    warm = cache.SegmentCache(tmp_path)
    assert warm.load_index() == {k}
    assert warm.get(k) == "トークナイザーはテキストを変換します。"


def test_one_edited_segment_invalidates_exactly_one_key(tmp_path):
    c = cache.SegmentCache(tmp_path)
    blocks = ["Para one.", "Para two.", "Para three."]
    for b in blocks:
        c.put(key_for(b), f"<ja>{b}</ja>")
    c.save_index()

    edited = ["Para one.", "Para two, revised.", "Para three."]
    keys = [key_for(b) for b in edited]
    known = cache.SegmentCache(tmp_path).load_index()
    misses = [k for k in keys if k not in known]

    assert len(misses) == 1
    assert misses[0] == key_for("Para two, revised.")


def test_key_changes_with_model_prompt_and_glossary():
    text = "Load a pretrained model."
    base = key_for(text)
    assert key_for(text, model_id="other/model") != base
    assert key_for(text, prompt_version="v2") != base
    assert key_for(text, glossary_sha="def456") != base
    assert key_for(text, language="ko") != base
    assert key_for(text) == base


def test_get_many_returns_only_hits(tmp_path):
    c = cache.SegmentCache(tmp_path)
    hit, missing = key_for("stored"), key_for("absent")
    c.put(hit, "保存済み")
    found = c.get_many([hit, missing])
    assert found == {hit: "保存済み"}


def test_unreadable_index_is_treated_as_cold_not_fatal(tmp_path):
    c = cache.SegmentCache(tmp_path)
    c.put(key_for("x"), "エックス")
    c.save_index()
    c.index_path.write_text("{ this is not json", encoding="utf-8")

    fresh = cache.SegmentCache(tmp_path)
    assert fresh.load_index() == set()  # degrades, does not raise


def test_index_rebuilds_from_blobs_on_disk(tmp_path):
    """save_index derives from blobs, so a lost index self-heals on the next write."""
    c = cache.SegmentCache(tmp_path)
    keys = {key_for(f"p{i}") for i in range(5)}
    for k in keys:
        c.put(k, "訳")
    c.index_path.unlink(missing_ok=True)

    assert cache.SegmentCache(tmp_path).save_index() == 5
    assert cache.SegmentCache(tmp_path).load_index() == keys
