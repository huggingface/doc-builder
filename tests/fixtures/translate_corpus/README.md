# Translation corpus fixture

Twelve real pages from `huggingface/transformers`, `docs/source/en`, copied here so the
masking round-trip runs on every CI run instead of only on a machine that happens to have a
Transformers checkout. They keep their original Apache-2.0 licence headers.

They are not a random sample. Each one is here because it broke something:

| page | what it covers |
| --- | --- |
| `model_doc/mms.md` | a ```` ``` ```` block closed with ` ```` ` -- a valid longer closer |
| `model_doc/mistral3.md` | the same, plus a fence whose info string is a bare `"` |
| `model_doc/deepseek_v3.md` | a `` `````` `` block, and a `[rank0]: ...` line inside a fence |
| `model_doc/gemma3n.md` | the only reference-style links in the docs, with their definitions |
| `community.md` | the most links with parentheses inside the URL |
| `model_doc/mixtral.md`, `model_doc/sam.md`, `model_doc/layoutlmv3.md` | more of the same |
| `model_doc/blt.md` | `[here](<INSERT LINK HERE>)` -- one placeholder nested in another |
| `model_doc/bert.md` | `[[autodoc]]` directives with indented member lists |
| `philosophy.md` | prose-heavy, so over-masking shows up as a low translatable ratio |
| `quicktour.md` | `<hfoptions>` tags, multi-line `<img>` tags, mixed prose and code |

To run the tests against a full checkout instead, point `EN_DOCS` at it:

```bash
EN_DOCS=~/hf/transformers/docs/source/en pytest tests/test_translate_segment.py
```
