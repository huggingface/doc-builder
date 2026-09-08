# Plan 001: Simplify the translation pipeline and preserve its correctness checks

> Executor: read this file fully, then implement its phases in order. Preserve the acceptance cases even when deleting the old abstractions. Do not commit, push, enable schedules, submit paid Jobs, or publish docs merely because those operations appear in the verification procedure. The user subsequently authorized local implementation; remote execution and rollout still require their instruction. Report blocked live verification separately from passing local tests.

> Scope amendment: all current changes must stay inside `/Users/steven/hf/doc-builder`. Do not edit Transformers, prepare a companion repository patch, change live schedules, or mutate remote services yet. Reading Transformers as the source corpus is allowed; modifying that checkout is not. The user confirmed that the viewing requirement means reading translated Markdown in the Hub file viewer, not opening a fully rendered doc-builder site. Output must be inspectable by clicking a file or folder in the Bucket without downloading/extracting an archive. The archive alone is not a sufficient deliverable.

## Status and scope of the decision

- Priority: P1. Effort: L. Implementation risk: medium; deployment risk: high if the archive handoff is enabled without a successful smoke build.
- Category: architecture, correctness, and migration. Dependencies: none.
- Planned on: 2026-09-06.
- doc-builder checkout: `/Users/steven/hf/doc-builder`, branch `ja-translation`, commit `f717365a865f4458463afdb411a2ca6556baa73a`.
- PR: <https://github.com/huggingface/doc-builder/pull/813>. Its head matched the checkout during this review.
- Read-only Transformers source checkout inspected: `/Users/steven/hf/transformers`, commit `58a94493a64f74d04279a3a617297dfe355b0b89`. No changes to this checkout are in scope.
- The user requested a detailed plan for the simplified design, including complete source validation, correct extraction, actual translation acceptance, cancellation/preview isolation, and dependency/rollout verification.

First run `git status --short` and `git diff --stat f717365a865f4458463afdb411a2ca6556baa73a..HEAD -- src/doc_builder/translate src/doc_builder/commands/translate.py src/doc_builder/commands/doc_builder_cli.py src/doc_builder/glossaries pyproject.toml setup.py uv.lock kit .github/workflows tests`. Inspect any drift before using the excerpts below. Preserve unrelated changes. A routine rebase is allowed during implementation, but do not blindly restore the old PR against a changed main branch.

## Local implementation result — 2026-09-06

Local implementation is complete and uncommitted. No remote Job, Bucket write, GitHub update, schedule change, or Transformers edit was performed. The maintainer path is documented in [Preview translated documentation](../docs/translation.md). A reachable doc-builder commit is required before the worker can fetch this implementation.

Verification:

- Full repository suite: **368 passed**, with five expected warnings from missing caches in stubbed cold-run tests. Ran the repository's single-worker xdist configuration; its existing external autodoc lookup used read-only network access.
- Pinned Transformers source `58a94493a64f74d04279a3a617297dfe355b0b89`: **743 Markdown pages** pass extraction, round-trip, and simulated-translation structural checks with Node 22.14.0. The combined parser/acceptance run passed 63 tests. The real `doc-builder translate --dry-run` also validates that complete tree. These are syntax checks, not Japanese quality measurements.
- Ruff lint and format checks, JavaScript syntax and Prettier checks, lock consistency, and `git diff --check` pass. The lock diff changes four dependency requirement lines without unrelated package upgrades. This machine's global uv age/index policy differs from the repository lock; verification used an explicit resolver config and the public PyPI index.
- Source checkout drift was detected during implementation. Corpus checks use a clean disposable copy under doc-builder's ignored `build/` directory; the user's existing Transformers checkout was left untouched.
- Existing kit dependencies provide mdsvex and Svelte parsing. Added regression cases cover nested Svelte expressions, literal brace prose, nested/escaped image labels, Unicode anchors, API headings, and cached-response acceptance.

Measured physical lines against original PR head `f717365a865f4458463afdb411a2ca6556baa73a`, including blank lines and comments and all new files:

| Scope | Before | After | Net removed |
| --- | ---: | ---: | ---: |
| Translation Python (command and package) | 2,585 | 1,006 | 1,579 |
| New kit JavaScript adapter | 0 | 333 | -333 |
| Touched build/test/preview workflows | 344 | 406 | -62 |
| **Production Python + JavaScript + workflows** | **2,929** | **1,745** | **1,184 (40%)** |
| Translation tests and harness, excluding fixtures | 2,669 | 1,077 | 1,592 |

Python alone shrank 61%; Python plus the new parser adapter shrank 48%. This is less than the original 65–80% estimate because it retains source validation, syntax acceptance, Job cancellation, complete archive verification, and the new manual workflow. Documentation, fixtures, lockfile, and packaging metadata are excluded from those implementation counts; deleting the duplicate 88-line setup.py is also excluded. Test counts changed because corpus checks now batch pages instead of parametrizing every old internal case.

All 29 inline review requirements have local regression coverage or have been removed structurally. Syntax and acceptance cases live in `test_translate_segment.py`, `test_translate_validate.py`, and `test_translate_adversarial.py`; stale output and cache cases in `test_translate_cache.py`; failed generation and result association in `test_translate_pipeline.py`; archive/disclosure and isolation in `test_translate_publish.py`; lifecycle and canonical cache ownership in `test_translate_job.py`; exact consumer wiring and existing HTML-cache flags in `test_translate_workflow.py`. The pointer, manifest repair, and in-process GC cases are resolved by removing those mechanisms, while their no-partial-publication outcomes remain tested.

**Still pending:** a real pinned GPU Job, generated Markdown click-through on the Hub, Japanese quality inspection, and a full accepted archive HTML build plus warm GPU/build-cache smoke. The documented Bucket URL shape and README behavior were checked read-only against the public Hub; no generated result has been claimed as live-tested. The runtime image and public continuous-batching API were checked against their published sources, but CUDA/model execution remains unverified. Enabling a Transformers caller and coordinating the legacy producer remain future work outside this scope.

## Live preview result — 2026-09-07

The user subsequently authorized pushing the doc-builder implementation, running Jobs in `hf-doc-build`, and writing preview results to `hf://buckets/hf-doc-build/doc-translate`. They selected `quicktour.md` and `models.md` and approved switching to Qwen3 after Gemma 4 proved incompatible with the pinned continuous-batching cache. Full-source translation waits for their review of the preview.

- [Completed Job](https://huggingface.co/jobs/hf-doc-build/6a9f6cdf259f8e97255ed8aa): 182 seconds running on `a100-large`. Both pages and the pruned sidebar passed acceptance. The worker and runner independently read back the loose files and archive; the runner verified provenance, inventory, and completion README.
- [Completed Bucket folder](https://huggingface.co/buckets/hf-doc-build/doc-translate/tree/previews/transformers/ja/local-1-9ec85d204462), with [quicktour.md](https://huggingface.co/buckets/hf-doc-build/doc-translate/tree/previews/transformers/ja/local-1-9ec85d204462/source/quicktour.md) and [models.md](https://huggingface.co/buckets/hf-doc-build/doc-translate/tree/previews/transformers/ja/local-1-9ec85d204462/source/models.md).
- Source: `8eaf75f84e0ef68ccdaac14b739ace53a962bbee`; doc-builder: `f8707b046bf04f523f3d753b09bfdd52787944c5`; model/tokenizer: `Qwen/Qwen3-30B-A3B-Instruct-2507` at `0d7cf23991f47feeb3a57ecb4c9cee8ea4a17bfe`.
- Archive: `hf://buckets/hf-doc-build/doc-translate/previews/transformers/ja/local-1-9ec85d204462/source.tar.gz`; SHA-256: `e91ad0dae8c40d559a8f58098b272f46a2ad355f9d923605a866da518993bddf`.
- Live failures led to bounded fixes: paired semantic tags for model input, restoring immutable content by tag ID, preserving callout framing and terminal punctuation outside generation, protecting parameter names, explicit terminology, and retaining accepted units during the single retry. Failed runs did not produce completed preview archives.
- Final repository suite: **378 passed**, with five expected cold-cache warnings. All **743** pinned corpus pages still pass extraction, round-trip, and simulated-translation structural checks.

Technical success is not language approval. Inspection found untranslated prose such as “interchangeable,” “model skeleton,” and “not” in `models.md`, plus wording that needs editorial review. The Bucket is private; API read-back succeeded, but the available in-app browser was logged out, so authenticated Hub click-through remains for the user. No HTML build, warm remote cache run, full-source translation, Transformers edit, serving change, or production activation is claimed. The shared translation cache remains unchanged by these previews.

## Objective and explicit tradeoffs

Translate the English Markdown/MDX sources in Transformers' `docs/source/en` into Japanese, with a language parameter that can later select other configured languages. Prepare generation with Transformers continuous batching on HF Jobs. Store reusable translations and ordinary translated source files in an HF Bucket, together with a completed archive for build transfer. Prepare an opt-in consumer in doc-builder's shared workflow that retains PR #800's HTML cache. Do not activate it from Transformers or change the current serving setup in this scope.

Cache a complete page rather than individual paragraphs. The model still receives prose units from that page. A one-line source edit retranslates that page; this is the intentional cost of removing segment indexes, blobs, and output reconciliation. Missing or invalid cache data means recomputation, never missing prose.

Treat one failed required unit as a failed update after one retry. Do not publish English fallbacks or combine last-good pages from different source revisions. Cache complete successful pages so the next attempt can reuse them. This simpler policy can hold back an update because of one persistently failing page; report that page rather than introducing percentage thresholds.

The translation scope is checked-in prose, navigation titles, and visible link labels. Code, identifiers, destinations, formulas, doc-builder directives, component attributes, and source files remain unchanged. Python docstrings expanded by `[[autodoc]]` remain English. Do not build a docstring translation pipeline as part of this refactor.

## Current implementation and evidence

| Path relative to doc-builder | Current role / relevant observation |
| --- | --- |
| `src/doc_builder/commands/translate.py` | 652 lines; cloning, planning, source checks, thresholds, fallbacks, manifests, previews, and publication |
| `src/doc_builder/translate/pipeline.py` | 604 lines; prompts, units, acceptance, glossary, assembly, sidebar, continuous-batching manager |
| `src/doc_builder/translate/segment.py` | 387 lines; ordered regex masking and nested placeholder restoration |
| `src/doc_builder/translate/validate.py` | 340 lines; placeholder, heading, link, glossary, and translation checks |
| `src/doc_builder/translate/cache.py` | 193 lines; segment index and per-segment blob files |
| `src/doc_builder/translate/publish.py` | 381 lines; generations, manifests, pointer, reconciliation, verification, and GC |
| `.github/workflows/build_main_documentation.yml` | Adds `translated_languages` and downloads `CURRENT` followed by its generation; already enables `--html_page_cache` and writes on trusted builds |
| `src/doc_builder/build_cache.py` | Existing page-level HTML cache; preserve its behavior |
| `kit/preprocessors/mdsvex/index.js` | Existing Markdown tree handling and rendered heading ID algorithm |
| `src/doc_builder/check_links.py` | Existing fragment checking and an approximation of renderer heading IDs; do not copy its parser into translation |
| `tests/test_translate_*.py`, `tests/translate_harness.py` | Existing unit, corpus, adversarial, and command-level tests |
| `tests/fixtures/translate_corpus/` | Thirteen vendored Transformers pages plus a README; preserve their licenses and useful coverage |
| `setup.py` | Reintroduced by this PR even though its base migrated to `pyproject.toml`; remove the duplicate metadata during refactor |

Small drift-check excerpts read at this head:

```python
# src/doc_builder/translate/cache.py:32 (signature)
def segment_key(masked_text, model_id, prompt_version, glossary_sha, language):
    ...

# src/doc_builder/translate/pipeline.py:273
class PagePlan:
    ...
    # Current code masks the whole page before splitting at blank lines.

# src/doc_builder/translate/publish.py:81
GENERATIONS = "generations"
MANIFESTS = "manifests"
POINTER = "CURRENT"
```

The shared workflow declares `commit_sha`, but the inspected package checkout does not use `ref: inputs.commit_sha`. It also checks out doc-builder main and executes `git pull origin main`. Pinning only the reusable workflow reference therefore does not pin the implementation being installed. Fix these specifically for the archive consumer, preserving existing callers' default behavior.

Transformers' current `build_documentation.yml` calls the shared workflow twice. `build_other_lang` includes `ja`. This is a dependency for a future cutover, not an instruction to edit it now. Leave every Transformers workflow and language list unchanged.

Repository conventions: Python >=3.10, argparse command registration, lazy GPU imports, Apache headers, pytest with `tmp_path` and `monkeypatch`, Ruff line length 119. Match `commands/translate.py`'s CLI entry pattern, but make the command raise/exit nonzero on failure: the parent CLI ignores function return values. Keep comments about invariants, not accounts of previous debugging sessions.

## Baseline verified while planning

- The existing six translation test modules: **1,001 passed in 1.93 seconds**, using the checked-in fixtures.
- Ruff check passed for the translation command, translation package, translation tests, and harness; Ruff format check reported 14 files already formatted.
- No source changes were made. No real GPU generation, remote Bucket writes, or rendered translation build was run.
- `uv lock --check --offline` could not complete because the sandbox denied access to the uv cache. This is an unverified check, not a stale-lock diagnosis.
- Installed `huggingface_hub` is 1.27.0. Inspected callable APIs include `run_job`, `run_uv_job`, `list_jobs`, `inspect_job`, `cancel_job`, `wait_for_job`, `download_bucket_files`, `batch_bucket_files`, and `sync_bucket`. **There is no top-level `upload_bucket_files` in this environment.** Use the installed/pinned SDK's actual API.
- A read-only mdsvex probe through `kit/node_modules/mdsvex/dist/main.cjs.js`, with highlighting and smartypants disabled, returned source offsets for headings, paragraphs, text, a multiline link with a parenthesized destination, inline code, and component tags. This proves the basic adapter entry point, not full corpus correctness. A direct import of the bundled ESM file failed in Node 24; use the supported CommonJS entry from the helper rather than that internal ESM path.
- `markdown-it-py` is available locally, but the inspected inline tokens do not carry source positions. Do not assume `token.map` provides the inline spans this design needs.

## Target code organization

Use a few concrete functions and ordinary dict/list values. Do not introduce backend interfaces, plugin registries, repositories, services, or classes for each pipeline stage.

| File | Target responsibility |
| --- | --- |
| `src/doc_builder/commands/translate.py` | Small argparse wrapper: validate arguments, call `run`, propagate exit status |
| `src/doc_builder/translate/pipeline.py` | Source inventory, page cache, requests, `generate_batch`, acceptance, assembly, artifact upload; keep helpers here unless one becomes independently substantial |
| `src/doc_builder/translate/segment.py` | Thin Python bridge to source-position extraction/reassembly and protected-content checks |
| `kit/preprocessors/translate.cjs` (new) | Small mdsvex adapter; JSON input/output; extract and validate against the original source; never invoke SvelteKit or write generated pages |
| `src/doc_builder/translate/job.py` (new) | Small GitHub-runner entry point: submit/wait/cancel the HF Job, validate returned metadata, update the canonical cache, emit workflow outputs |
| `src/doc_builder/translate/artifact.py` (new only if needed) | Shared archive verification/install helper used by the runner and build workflow; otherwise keep it as functions in `pipeline.py` |
| `src/doc_builder/translate/__init__.py` | Short package description, no orchestration |

Delete `publish.py`, the segment-cache implementation in `cache.py`, and `validate.py` after their needed checks are moved into acceptance/extraction. Do not retain compatibility wrappers for an unmerged PR's old internal API. Retarget useful tests to outcomes rather than preserving old object names.

The earlier estimate was 580–880 lines of replacement Python. Treat approximately 750 as an aspiration, not an acceptance gate. The source-position adapter and cross-repository cancellation workflow may raise the total. Report Python, JavaScript, and changed YAML separately and together so code moved to another language does not masquerade as deletion.

## Data and execution contracts

### Inputs and one source of truth

The manual doc-builder preview workflow takes an explicit full Transformers commit SHA and pins its doc-builder implementation SHA. Do not use `github.sha` as the Transformers revision in a workflow running from doc-builder: that SHA belongs to doc-builder. Resolve the model and tokenizer revision to immutable commits before generation. Keep the existing model choice initially unless a later authorized live smoke test proves it unusable; do not pick another model to make a unit test pass.

Proposed CLI surface (these are target arguments, not commands available at the current head):

```text
doc-builder translate transformers
  --source-revision <transformers-sha>
  --lang ja
  --bucket hf://buckets/<namespace>/<bucket>
  --run-id <unique-id>
  [--source <local-docs-source>] [--pages-file <file>] [--dry-run]
```

Use one small versioned configuration in `pipeline.py` (ordinary constants/dicts, plus the existing `glossaries/<lang>.yml`) for language name, model/tokenizer IDs and pinned revisions, prompt, glossary, and generation defaults. Do not introduce a configuration loader framework. Keep model/attention overrides only if needed for actual smoke runs; remove the four failure percentages, `--rebuild`, and knobs with no demonstrated user need. Local source overrides and selected-page previews cannot claim to be full production snapshots.

### Page cache

Canonical location: `cache/transformers/ja.json`. The file is a plain mapping from digest to complete translated page text before disclosure insertion. Cache `_toctree.yml` as one analogous document, retaining paths and changing only titles. No segment blobs or separate index.

Digest inputs are canonical JSON containing package, relative file path, complete source bytes/hash, target language, pinned model and tokenizer revisions, generation settings, glossary contents, prompt version, and extraction/validation version. The config version must cover retry behavior, anchor rules, and assembly changes. Do not include the repository commit itself: identical pages should be reusable across commits. Do not hash only masked text.

Cache reuse must pass type, extraction/structure, protected-content, and per-unit translation acceptance against the matching source. Invalid entries are misses. Validation should use the same extraction/acceptance functions as fresh generation. A syntactically valid JSON string is not evidence of a usable page. No source text or old-generation fallback is inserted to fill a missing value.

At run end retain entries for the current inventory/config plus complete newly translated pages; no unbounded cache-history index or GC service. Cache-read failure warns and becomes an empty cache. A failed cache write warns and costs future recomputation; it must not falsely certify a translation artifact. On a normal translation failure, upload the complete-page cache candidate before exiting nonzero, so successful pages can be retained by the runner. On a hard crash, losing work since the last upload is an accepted simplicity tradeoff.

### Bucket artifacts and ownership

```text
cache/transformers/ja.json                    # only GitHub runner updates this
runs/transformers/ja/<run-id>/cache.json      # candidate, only this HF Job writes it
runs/transformers/ja/<run-id>/source.tar.gz   # only present after full acceptance
runs/transformers/ja/<run-id>/source/         # ordinary .md/.mdx, sidebar, and assets
runs/transformers/ja/<run-id>/README.md       # Hub-readable entry point, uploaded last
```

Use a fresh run ID including GitHub run ID, attempt, and a random suffix; language is part of the prefix. A manual retry gets a new prefix. Preview runs use `previews/...`, cannot update the canonical cache, and cannot be passed to the production consumer.

The loose `source/` files and archive must come from the same accepted local tree, with no second translation/rendering pipeline. Upload those files to the unique run prefix, verify their relative paths and bytes against the archived tree, and write the run README only after both uploads succeed. Include the language, source revision, preview/full status, and links to the translated pages in the README. Print the verified Hub folder URL and at least one page URL in the result. Never claim an incomplete run folder is a completed translation; builders continue to require successful Job completion and the verified archive. Partial files can be visible while an upload is in progress, so the README is a human completion cue, not a publication pointer or a substitute for build validation.

The Hub documents directory navigation and rendering a directory's `README.md` below its file list: <https://huggingface.co/docs/hub/storage-buckets#browsing-buckets-on-the-hub>. The user explicitly selected reading translated Markdown in the Hub file viewer. Preserve `.md`/`.mdx` as ordinary readable files and verify direct file links during authorized smoke testing; custom doc-builder syntax may appear as source in this view. No rendered-site preview, new host, or additional renderer is required. The existing HTML build remains a separate correctness/integration check.

The HF worker reads the canonical cache, generates, and uploads only into its run prefix using explicit SDK transfers. Do not rely on `os.replace` being atomic on a Bucket mount. The canonical cache is written only by the serialized GitHub runner after inspecting that Job's terminal state and validating the candidate. A handled translation failure may contribute validated complete pages; a canceled/deleted Job or missing/incomplete candidate contributes nothing. A late orphan can therefore write only unused run files.

The archive contains `source/` (the complete target-language source tree) and a small `metadata.json` with format version, package, language, source SHA, doc-builder SHA, config digest, run ID, and `preview` boolean. This is provenance for one artifact, not a source/output reconciliation manifest. Compute an archive SHA-256 in the runner and pass it to the consumer. Missing upload, wrong identity, wrong hash, or preview metadata aborts before replacing the checkout's language folder.

The worker must finish the archive and browsable-file uploads before returning success. The runner must observe successful Job completion and download/verify the exact archive before exposing outputs. The consumer downloads into a temporary directory, verifies hash and metadata, extracts only regular files/directories under `source/`, checks the sidebar/inventory, then replaces `docs/source/ja` in its disposable build checkout only. It must not modify the user's existing Transformers checkout. Reject archive traversal, links, and unexpected members using the standard library's available extraction filter plus explicit layout checks; do not write a general archive framework. Dereference valid repository symlinks while assembling the archive so no archive symlinks are necessary.

There is no `CURRENT`, generation promotion, in-place repair, live-directory sync, or per-run artifact deletion. Retention is deferred until actual storage use justifies a separate policy. Existing served HTML remains governed by the existing serving workflow: removing a source page removes it from the new tree/sidebar, but this refactor does not promise to purge every historical URL or delete assets retained for #800 cache reuse.

### Extraction and structural preservation

Use the installed mdsvex parser from the same pinned kit used to build docs. The `.cjs` helper should `require("mdsvex")`, capture the tree through a remark plugin, and discard compiler output. Disable highlighting and smart punctuation for source-span extraction. Send pages in one JSON batch to a short-lived helper; do not launch Node once per paragraph or add an RPC server. Use the existing `locate_kit_folder()` pattern; document the checkout, Node, and `npm ci --prefix kit` prerequisites rather than building another package-distribution mechanism.

Source positions are JavaScript UTF-16 offsets. Perform source slicing/replacement in JavaScript, or explicitly convert offsets at the boundary. Never apply raw JS offsets to Python Unicode strings. Test astral characters before and inside a translated unit.

The adapter keeps block structure outside generation: headings, paragraph containers, list markers/indentation, table separators, code fences, and component boundaries. A unit is a complete prose-bearing inline container, not each isolated text leaf. Preserve natural context across inline links and code. Do not translate `Read ` and `the guide` as unrelated requests merely because the AST has separate text nodes.

Inline protected elements use placeholders with a per-unit namespace that cannot collide with the source. Keep opaque elements such as inline code or an API reference indivisible. Represent formatting and link wrappers as typed pairs whose identity and nesting can be checked. The model may move complete inline elements for Japanese word order; it may not swap an opener with a closer, change image kind, move structural content between blocks, or add new markup. Validate pair nesting and payload identity, not just a sorted bag of marker numbers. The source skeleton and parsed restored structure must agree after normalizing allowed prose changes and intentional anchor insertion.

Handle doc-builder extensions in one narrow adapter table, grounded in the README and converter: `[[autodoc]]` plus its member lines (including indentation and intervening blanks), API cross-references, custom anchors, callout markers, component tags/attributes, literalinclude payloads, and supported math forms. Preserve HTML/Svelte expressions and code-bearing payloads. Extract visible prose inside components; do not mark an entire `<Tip>...prose...</Tip>` or `<hfoption>` body opaque. Generic HTML nodes may contain both tags and prose: that is a mandatory corpus case, not permission to skip the body.

Preserve complete link/image destinations, labels, reference IDs/definitions, code, and math according to source provenance. Link labels and image alt text remain translatable; attributes stay unchanged for v1. Reference identifiers are not prose. Protect bare URLs as known source spans and delimit them so Japanese particles cannot become part of the rendered href; if rendering requires wrapping a bare URL as an explicit autolink, make that one documented normalization and test actual rendered hrefs. Do not rescan Japanese prose with the old permissive URL regex.

Calculate the original rendered heading ID and append `[[original-id]]` when translating a heading without an explicit anchor. Match the renderer's Unicode-aware slug behavior and `getTitleText` semantics; do not implement the README's obsolete ASCII-only description. Preserve existing custom IDs. Test inline formatting, Unicode, setext headings, and headings adjacent to autodoc expansion. Headings with no usable source ID require an explicit handling decision; do not invent incompatible IDs silently.

### Acceptance and inference

One acceptance function applies to fresh responses, retries, cache hits, and sidebar titles. A required prose unit must be present, have nonempty non-placeholder content, preserve protected elements, pass the reconstructed-structure check, and not be an English echo after whitespace normalization. No blanket rule that unchanged short text is acceptable. A unit consisting entirely of configured keep terms, numbers, or protected elements is deliberately excluded from translation before requesting it. Product/API names qualify only when explicitly configured or identified by source syntax such as code/API references; do not guess from capitalization or short length. Ordinary prose including short sidebar labels still requires translation.

Implement glossary `keep` by protecting its matches in the input, rather than merely warning after generation. Put relevant `pin` renderings in the prompt and validate occurrences where applicable. Store both in the config fingerprint. Boundaries must avoid matching a short keep term inside an unrelated word. Language selection is an explicit code-to-name/config mapping; unknown codes fail before loading the model. Adding a language supplies its name, glossary/disclosure, and any necessary generation defaults, not another pipeline.

Collect requests for all cache-miss pages, tokenize with `return_dict=False`, and call public `generate_batch()` in bounded groups. Keep GPU imports/model initialization behind the nonempty-miss branch. Use a single conservative attention/compilation configuration proven for the selected model; do not retain custom workload-hint imports just for tuning. Reuse the loaded model across groups.

Enforce input plus output budgets before generation. Split oversized prose at sentence/paragraph boundaries without dividing placeholders, paired inline elements, or Unicode characters; if no safe split exists, fail with page and unit context instead of truncating the input. Use a bounded output allowance and check generation errors and termination. A response that exhausts its output cap without a valid terminal condition must not pass because its markers happen to survive.

At the inspected Transformers source, `generate_batch()` returns results in input order but may omit missing requests. **Never zip an incomplete result list against all inputs.** If a group's result count is wrong or any result reports failure, treat that group as failed for assignment and retry it once; do not misattribute later results to earlier pages. On a complete successful group, assign in the verified input order. Prove this behavior at the pinned dependency version with stub/integration tests before relying on it.

Allow one retry per failed unit/group, with a documented bounded extra output allowance for truncation. The retry prompt/settings are part of the configuration identity. Reject further failures and exit nonzero. Strip only a documented, tightly delimited model reasoning envelope if the selected model requires it; do not accumulate model-specific repair regexes or quietly delete arbitrary unexpected bracket text.

### Complete source and preview rules

Clone/check out the exact source SHA, including repository files targeted by docs symlinks. Derive the Markdown/MDX inventory from that checkout, not only from files that happen to be readable during a directory walk. Check every expected file can be read, require a nonempty inventory and readable sidebar, and resolve every local sidebar entry to exactly one supported source file. Catch a missing unlisted page as well as a missing listed page. Read errors abort the run.

Preserve `_toctree.yml` hierarchy and `local` values; translate only string title values and verify a YAML round-trip. An empty/missing title response is a failure. Copy supporting assets and language-local configuration from English; root-level shared configuration is supplied by the same source checkout. Resolve symlinks within the repository, copy their bytes, and report missing or external targets. Do not treat a broken source symlink as a deleted English page.

For `--pages-file`, validate every selected path, reject an empty/no-match selection, and prune the sidebar only in the isolated preview tree. Mark preview provenance explicitly and use the same acceptance/failure rules. Partial previews can leave links to nonselected pages unresolved; report that preview limitation, but do not weaken production completeness checks or redirect production links to make a preview build pass.

## Implementation phases and verification gates

### Phase 1 — Freeze regression expectations and prove the extractor

Read the six existing translation test modules and retain their behavioral cases in a test matrix. Implement the mdsvex adapter in `kit/preprocessors/translate.cjs` plus its bridge in `segment.py`. Do this before rewriting cache or publication. Add source-offset tests and a representative `.mdx` fixture. Add tests that assert specific prose remains model-visible, since identity round-trips alone pass even when prose is incorrectly masked.

Install kit dependencies with its existing lockfile in the executor's environment; use the pinned Node runtime used for the smoke build. Prefer the existing parser rather than adding tree-sitter, a second AST framework, or a Node service. The CommonJS extraction probe demonstrated basic feasibility only: supported raw component bodies, doc-builder directives, tables, reference labels, and protected math must pass the fixture gate before this choice is considered complete.

**Verify:** `.venv/bin/python -m pytest tests/test_translate_segment.py tests/test_translate_validate.py tests/test_translate_adversarial.py -q` → all retained syntax cases and new source-position/structure cases pass; no skips caused by missing Node/kit in configured translation CI. Also run `EN_DOCS=/Users/steven/hf/transformers/docs/source/en .venv/bin/python -m pytest tests/test_translate_segment.py -q` locally → all discovered pages pass extraction and visibility checks; record the corpus commit and count. Pure source identity tests should bypass deliberate anchor/disclosure changes; normalization tests must check those changes separately.

If the adapter requires patching mdsvex internals or a large second parser, stop this phase and report the failing constructs with examples. Do not spend the rest of the refactor building around an unproven extractor. A small explicit doc-builder extension is acceptable; silently excluding troublesome pages is not.

### Phase 2 — Implement page cache and generation acceptance

Replace segment storage with the page-cache dict and fingerprint contract above. Keep no legacy cache migration: use the new namespace/config identity and start cold. Implement a complete-source inventory, toctree title units, pre-generation keep-term exclusion, generation budgets, one retry, and the public `generate_batch()` adapter. Stub only the model boundary in tests; source processing and acceptance must run for real.

Test a cold run, a warm run that never loads a model, a one-page edit, code/URL-only edits, page deletion, paragraph reordering, invalid cached values, and prompt/model/glossary version changes. On any source/read/acceptance failure, assert there is no production archive. Persist only complete accepted pages to the candidate cache. A page spanning several generation groups is not cached until all its units succeed.

**Verify:** `.venv/bin/python -m pytest tests/test_translate_cache.py tests/test_translate_pipeline.py tests/test_translate_publish.py -q` → all page-cache, source, generation, and failure-policy cases pass with no GPU/network. The warm-run test must fail if model/tokenizer initialization is attempted; one failed request out of one must exit nonzero.

### Phase 3 — Implement run artifacts and remove old publication machinery

Assemble each accepted snapshot from scratch in a temporary local directory. Add the disclosure after translation validation, archive `source/` with metadata, and upload both the archive and the loose `source/` files to the exact run path. Generate the run README from the accepted page inventory after verifying both forms. Add a standard-library archive verifier/installer reused by tests and the workflow. On handled failures upload the complete-page cache candidate, then propagate nonzero status. Do not upload an archive or present a completed Hub entry point before full acceptance.

Replace tests for `CURRENT`, manifests, repairs, and GC with tests showing that their failure modes are impossible through the new interface: remote writes never target shared/live paths, canceled and failed runs never yield build outputs, and a new successful run needs no existing translated output. Keep negative tests for missing upload, corrupt archive, wrong source SHA, wrong language/config/run ID, malicious members, and preview artifacts.

Delete `publish.py`, the old cache module, obsolete validation code, threshold flags, compatibility-only tests, and misleading long comments. Update `translate_harness.py` to return real Japanese stand-in prose and targeted corruptions; appending punctuation to English must not be the only fake translation that proves acceptance.

**Verify:** `.venv/bin/python -m pytest tests/test_translate_publish.py tests/test_translate_adversarial.py -q` → interrupted-upload and wrong-artifact cases fail before installation; complete archives install into a fresh directory; previous served output is untouched by producer failures. `rg -n 'SegmentCache|KEEP_GENERATIONS|SEGMENT_GATE_MIN_ATTEMPTS|read_pointer|gc_generations|min.page.coverage|min.segment.success|max.failure.rate|warn.failure.rate' src/doc_builder/translate src/doc_builder/commands/translate.py` → no old machinery remains (exit 1 means no matches).

### Phase 4 — Add the Job runner and archive consumer

Implement `python -m doc_builder.translate.job` as the runner entry point with the same small config, package/language, source SHA, and unique run identity. It should use `run_uv_job` or `run_job` from the selected pinned Hub SDK, not shell-parse human logs to discover Job IDs. Pass secrets via the Jobs secrets argument; do not embed tokens in archive metadata, prompts, logs, workflow outputs, or command strings.

Production concurrency is a GitHub workflow group per package/language, with `cancel-in-progress: false`, covering submission through build completion. Only that runner promotes cache candidates. Label remote Jobs with package, language, workflow purpose, and run identity. At startup, inspect matching earlier nonterminal Jobs and cancel/wait for their terminal state before submitting a new one; if status cannot be established, fail visibly rather than launching an overlapping authoritative run. The SDK's wait function returns failed terminal states too: explicitly require `COMPLETED` before enabling the build.

Record the Job ID immediately after submission. An `always()` cancellation step should cancel the recorded Job if it has not reached a terminal state. Set a finite remote timeout shorter than the enclosing GitHub timeout with room for cleanup and artifact download. Cancellation hooks are best effort, so the run-specific write boundary remains the correctness protection when a runner dies between submission and recording the ID. Next-run label discovery and the remote timeout handle that orphan. No Bucket lock/CAS protocol is needed.

The worker runtime needs Python/CUDA dependencies, the pinned doc-builder checkout, Node, and kit dependencies for extraction. Pin a known compatible GPU image/runtime and provision Node from a pinned distribution in the bootstrap; reuse the existing kit lockfile. Do not introduce a custom image build pipeline unless a measured bootstrap failure makes it necessary. Verify the exact Node/runtime/Hub/Transformers combination before rollout; do not assume a Python-only base image contains Node.

Replace `translated_languages` with explicit optional archive inputs in `build_main_documentation.yml`: `translation_archive`, `translation_archive_sha256`, `translation_language`, and `doc_builder_revision`. Reuse its existing `commit_sha` for source identity. Require these together when an archive is supplied; v1 supports one translated language per call and requires `languages` to equal that language. Future languages use independent workflow calls, not a language-list parser in this feature.

For archive builds, set the library checkout ref to `inputs.commit_sha` before installing the library. Check out doc-builder at `doc_builder_revision` and skip the later `git pull origin main`. Existing callers without archive inputs retain their default behavior; do not globally change workflow pinning as an unrelated migration. Fetch and verify the archive, then call the shared installer before the normal build step. Preserve `--html_page_cache hf://buckets/hf-doc-build/doc-build-cache --html_page_cache_write` and the current publication steps.

**Verify:** create `tests/test_translate_job.py` and `tests/test_translate_workflow.py`. Run `.venv/bin/python -m pytest tests/test_translate_job.py tests/test_translate_workflow.py tests/test_build_cache.py -q` → fake Job lifecycle, success-only outputs, failed-run cache recovery, cancellation-before/after-ID-recording, orphan discovery, nonterminal refusal, wrong artifact, pinned-checkout, and nontranslated-caller cases pass. YAML tests must understand YAML's `on` key correctly; use a suitable loader. Test helper behavior as well as workflow wiring, not only text searches for field names.

### Phase 5 — Prepare a doc-builder-only manual preview workflow

Prepare `.github/workflows/preview_translation.yml` inside doc-builder. Use manual dispatch only, with inputs for the full Transformers source SHA, language, selected pages, and the approved preview Bucket prefix. Resolve the doc-builder implementation revision from this workflow's own checkout. Invoke the Job runner and return the completed Hub folder/page links. Do not add a production schedule, a caller in Transformers, or an upload to the existing live docs namespace.

Any local HTML smoke build uses an ignored disposable source checkout under doc-builder, never `/Users/steven/hf/transformers`. The shared workflow's live upload steps must not run for preview verification. Test the shared installer/build helpers directly in this preview workflow instead of adding a new serving mechanism. The actual Job/Bucket upload and workflow dispatch remain future operations, requiring authorization beyond this plan-only update.

Do not ingest the old flat Bucket or generation tree as trusted cache data. Do not disable the old standalone nightly HF schedule or change any existing remote Job. Keep the new producer/consumer isolated until a later explicit production-cutover request. A future Transformers caller must coordinate Japanese ownership and disable the legacy producer; document that dependency briefly, without preparing a cross-repository patch now.

**Verify:** the doc-builder preview workflow parses, has no schedule or live-serving upload, distinguishes source SHA from implementation SHA, and emits Hub links only after verified completion. Tests compare loose translated files with the archived files and require a completed README plus valid page links. Assert no Transformers file changes are part of this patch. Actual Hub click-through testing is a separately authorized live gate; do not claim it passed from API-only or local tests.

### Phase 6 — Consolidate dependencies, documentation, and tests

Use `pyproject.toml` as the only Python metadata source and remove the reintroduced `setup.py`. Keep GPU dependencies in the `translate` extra and imports lazy. Pin minimum compatible library APIs in package metadata and exact tested versions/revisions in the worker runtime. Do not infer compatibility from the current environment alone or retain the WorkloadHints version floor without checking whether it is still needed. Regenerate `uv.lock` intentionally in the implementation environment; never let a routine test invocation silently rewrite it.

Add Node setup and `npm ci --prefix kit` to the translation test environment so parser/corpus checks run on Linux and Windows. Missing parser prerequisites must fail the configured translation suite, not skip the important cases. Keep the fixture corpus under version control. The full Transformers corpus remains an additional explicit local/live gate with its source SHA recorded.

Use `docs/translation.md` as the one maintainer guide, linked from the README's multilingual section. Explain prerequisites, the shortest dry-run/preview/full-run path, how to open the output folder/page on the Hub, cache invalidation, the failed-update policy, how to inspect one failed page, and the English-autodoc boundary. State that Transformers integration and production cutover are deferred. Include one usable diagram and one pinned-runtime example verified by the smoke run. Keep internal schemas and the complete regression matrix in tests/this plan instead of burdening the operator guide. Invoke docs-design when writing that guide and cli-ux for the changed CLI strings.

**Verify:** run the command matrix below. Require the translation/corpus/helper tests, relevant build-cache/check-links tests, Ruff, formatting, lock check, and clean packaging metadata. Update the PR description around the final implementation only when separately authorized to update GitHub; remove old flat-tree preview commands and percentage-gate claims at that point.

## Mishig review acceptance matrix

The numbers identify inline comments in PR #813; append them to `https://github.com/huggingface/doc-builder/pull/813#discussion_r`. These are regression requirements from earlier reviewed heads, not a claim that every bug still exists at the planned head.

| Review comment | Required regression / new contract |
| --- | --- |
| 3862407648 — longer closing fences | Three-backtick opener/four-backtick closer, tilde fences, quoted/list-contained fences, and arbitrary valid fence lengths preserve code while following prose remains translatable |
| 3862407654 — warm cache stale output | Code/URL/tag-only edits, paragraph removal/reordering, deleted files, and a missing previous output all produce the correct fresh tree without a reconciliation manifest |
| 3862407658 — wrong prompt markers | Prompt examples and extraction share marker definitions; changed rules invalidate the page cache |
| 3862407666 — empty output | Empty/whitespace/marker-only units and sidebar titles fail before caching, including corrupted cache hits |
| 3862407667 — partial destinations | Parenthesized URLs and reference destinations remain complete; compare exact protected values and link/image identity |
| 3862407673 — live writes/total failure | No run-specific partial write changes served docs; 100% failure gives no successful archive/output; new tree excludes deleted pages |
| 3879632518 — unreadable/empty source | Missing expected files, transient read errors, empty/wrong source root, and broken symlinks abort before generation/publication |
| 3879632522 — partial generation | Missing/interrupted upload cannot reach the consumer; install only a verified complete archive into a clean staging directory |
| 3879632527 — disclosure mismatch | Validate translated source before deterministic disclosure insertion; cached pages do not accumulate banners or enter old-page fallback logic |
| 3879632532 — hidden failed requests | One failed body unit or sidebar title fails the update even when every other page is cached |
| 3879632539 — nested badge images | `[![Open In Colab](badge.svg)](notebook.ipynb)` preserves both destinations and image kind; deleting `!` fails |
| 3879632549 — bare URLs | Entire raw URL is protected; destination changes fail; Japanese-adjacent prose does not extend the rendered href |
| 3879632555 — inline math | Protect `$...$`, `$$...$$`, and doc-builder's escaped-parenthesis form, including supported multiline cases |
| 3907950380 — dangling sidebar | Every production `local` resolves to exactly one planned `.md`/`.mdx`; preserving a dangling sidebar is failure |
| 3907950389 — damaged live repair | Every run gets a fresh artifact; never modify an archive being consumed or repair a live directory |
| 3907950394 — temporary writer collision | Local temps are unique; remote writes are run-scoped; worker cannot write canonical cache; no FUSE rename atomicity assumption |
| 3907950400 — pointer read race | No pointer lookup; the dependent build receives one exact run artifact |
| 3907950408 — stale manifest overwrite | No shared publication manifest; cache candidates cannot change selected build artifact identity |
| 3907950412 — GC removes active generation | No artifact GC during translation or building; retention work is deferred |
| 3907950417 — indexed missing blob | Cache values are read/validated before excluding pages; missing/invalid data is a miss, never a permanently English paragraph |
| 3907950421 — English echo counted | Echoed meaningful prose fails even if its heading translated; explicitly classified keep-only units are exempt before generation |
| 3907950426 — small-batch blind spot | One request and one failure returns nonzero with no production archive; no minimum-attempt threshold |
| 3907950432 — soft breaks in labels | `[technical\nreport](url)` remains a valid link; whitespace reflow cannot hide a lost opener |
| 3907950438 — nested closing brackets | `[huggingface_hub[cli]](url)` cannot lose a nested opener and pass merely because its URL survived |
| 3907950446 — Japanese URL rescan | Validate known protected spans; no false lost/gained result from appending Japanese particles to surrounding prose |
| 3907950455 — reference-image kind | `![Diagram][fig]` cannot become `[Diagram][fig]`; reference IDs stay unchanged while labels translate |
| 3907950464 — prices mistaken for math | `US$5 to US$10`, `$5-$10`, `$5/$10` leave intended prose visible; `$x$` remains protected |
| 3907950467 — false-success preview | Empty selections and rejected preview units fail; preview cache/artifact cannot replace production state |
| 3907950474 — unseeded format | Consumer cannot run until the exact new-format artifact exists, is verified, and matches successful producer identity |

Review-summary follow-ups: verify `.mdx` support, glossary `keep` behavior, a compatible Transformers/Hub/runtime pin, regenerated lockfile, representative corpus tests in CI, and a real GPU/Bucket/build smoke. Structural tests do not prove Japanese translation quality; record a small bilingual quality review separately from technical pass/fail where available.

## Commands and expected results

Run from `/Users/steven/hf/doc-builder` unless stated otherwise. Existing-environment checks use `.venv/bin/python` to avoid an implicit dependency sync. During implementation only, use the repository's `uv sync --extra all` / `uv sync --extra quality` patterns deliberately; adding the translation extra and kit install belongs to the explicit environment setup. Windows CI uses `uv run python`/the platform interpreter equivalent.

| Purpose | Command | Expected result |
| --- | --- | --- |
| Baseline/current translation tests | `.venv/bin/python -m pytest tests/test_translate_segment.py tests/test_translate_validate.py tests/test_translate_pipeline.py tests/test_translate_cache.py tests/test_translate_publish.py tests/test_translate_adversarial.py -q` | Existing baseline 1,001 pass; after refactor all retained outcomes pass even if test count changes |
| New runner/consumer tests | `.venv/bin/python -m pytest tests/test_translate_job.py tests/test_translate_workflow.py -q` | All stubbed lifecycle and consumer tests pass after these files are added |
| Full new translation suite | `.venv/bin/python -m pytest tests/test_translate_segment.py tests/test_translate_validate.py tests/test_translate_pipeline.py tests/test_translate_cache.py tests/test_translate_publish.py tests/test_translate_adversarial.py tests/test_translate_job.py tests/test_translate_workflow.py -q` | All pass; no GPU/network required; fixture cases do not skip |
| Adjacent regressions | `.venv/bin/python -m pytest tests/test_build_cache.py tests/test_check_links.py tests/test_convert_md_to_mdx.py -q` | All pass; compare unrelated baseline failures separately |
| Python lint | `.venv/bin/python -m ruff check src/doc_builder/commands/translate.py src/doc_builder/translate tests/test_translate*.py tests/translate_harness.py` | Exit 0 |
| Python formatting | `.venv/bin/python -m ruff format --check src/doc_builder/commands/translate.py src/doc_builder/translate tests/test_translate*.py tests/translate_harness.py` | Exit 0 |
| Adapter syntax | `node --check kit/preprocessors/translate.cjs` | Exit 0 |
| Adapter formatting | `cd kit && npx --no-install prettier --check preprocessors/translate.cjs` | Exit 0; installed kit dependencies required |
| Lockfile | `uv lock --check` | Exit 0 in an authorized network/cache environment; report inability to run separately |
| Patch hygiene | `git diff --check` | Exit 0 |
| Scope | `git status --short` and `git diff --stat` in doc-builder | Only the approved doc-builder implementation paths changed; no other checkout is modified |

The existing overall CI runs `uv run python -m pytest -n 1 --dist=loadfile -s -v ./tests/`, `uv run ruff check . --output-format=github`, and `uv run ruff format --check .`. Run them once after focused checks pass, or report the specific environment blocker; do not substitute a stubbed translation pass for full required CI.

## Live smoke and rollout gates

These are future execution steps, not actions performed while writing this plan. Use a scratch Bucket prefix and non-serving build output first; production activation requires a separate explicit instruction. Do not call the existing shared workflow unmodified as a smoke test if it uploads into the live serving namespace.

1. Record the exact Transformers SHA, doc-builder SHA, model/tokenizer revisions, Node version, GPU image digest/flavor, Python, Transformers, Hub SDK, and kit lock hash. Verify gated-model access without exposing tokens.
2. Once remote testing is explicitly authorized, run a real HF Job for a representative selected-page preview using the vendored edge cases plus actual Transformers pages. Confirm the archive/candidate and loose translated pages are readable via Bucket API. Open the Hub run folder and follow a README link to a translated page; record the actual reading experience, including whether custom syntax is displayed as source. API downloads alone do not satisfy the Hub-viewing requirement.
3. Install the archive into a disposable checkout under doc-builder through the same verifier the eventual consumer will call. Perform an actual HTML build with `doc-builder build transformers <docs/source> --language ja --version main --html --build_dir <scratch> --html_page_cache <scratch-cache> --html_page_cache_write`. Supply the normal light-install/mock-dependency prerequisites used by the shared workflow. Do not upload this smoke build to the serving bucket or modify an existing Transformers checkout.
4. Check rendered links/anchors, image href/src, component bodies, table/list structure, code, sidebar, disclosure, and representative Japanese text. Preview cross-links to deliberately omitted pages are reported explicitly. Run a full-source archive/build before production cutover so subset success cannot hide missing sidebar pages or unsupported syntax.
5. Run again unchanged: no model initialization/generation, a newly verifiable source artifact, and HTML-cache reuse consistent with unchanged generated MDX. Do not demand 100% HTML hits where the existing builder has documented nondeterministic output.
6. Change one source paragraph: only that page needs inference. Repeat with code-only change, a page deletion plus sidebar update, and a glossary/config version bump; verify both cache invalidation and the rebuilt source tree.
7. Inject a one-unit failure, malformed cache entry, interrupted archive download, cancellation, and wrong source metadata using stubs locally; the real smoke must at least demonstrate a failed Job does not invoke publication. These checks should not require repeatedly paying for GPU failures.
8. Stop at a verified doc-builder implementation and, when authorized, a readable Hub preview. Production ownership changes, legacy-schedule changes, and enabling a Transformers caller remain deferred. Record these as future integration work, not reasons to modify another repository or remote service now.

Record the smoke Job URL, Hub folder and page URLs, artifact path/hash, build result, cache-hit counts, and any unverified viewing or language-quality limitations in the implementation report. No live pass may be inferred from local stubs.

## Authorized implementation paths for a later executor

In doc-builder only: `src/doc_builder/commands/translate.py`, `src/doc_builder/commands/doc_builder_cli.py` if registration changes, `src/doc_builder/translate/`, `src/doc_builder/glossaries/ja.yml`, `kit/preprocessors/translate.cjs`, `pyproject.toml`, `setup.py` (delete), `uv.lock`, `.github/workflows/build_main_documentation.yml`, `.github/workflows/preview_translation.yml` (new, manual only), `.github/workflows/test.yml`, the translation test modules/harness/fixtures, `README.md`, `docs/translation.md`, and this plan's status.

No paths in Transformers or another repository are in scope. Do not prepare a companion patch in another checkout or stash such a patch elsewhere. Read source corpus files without modifying them; create any mutable test/build copy inside doc-builder's ignored scratch area.

Out of scope: #800 cache internals, renderer semantics, general link-checker refactoring, English docs rewrites, model code/docstrings, deleting existing Japanese Git sources, changing unrelated languages, introducing new cloud infrastructure, publishing review comments, or modifying live schedules/secrets/Buckets during plan preparation. Refer to existing renderer/helper code for behavior; no changes to `kit/preprocessors/mdsvex/index.js` or `check_links.py` are needed merely to reuse their rules.

If a separate worktree is needed for implementation, use a `codex/` branch such as `codex/simplify-translation` and preserve the user's current checkout. Keep logical changes reviewable. Do not commit or push by default; follow the user's implementation instructions when they arrive.

## Completion checklist and stop conditions

- [x] Source extraction passes all applicable existing corpus/adversarial cases, added `.mdx`/Unicode-offset/component-body/anchor cases, and a full pinned Transformers corpus pass.
- [x] Page cache is the sole translation cache; cached values are validated and invalid entries cause recomputation.
- [x] Cold/warm/change/delete/failure/preview outcomes meet the contracts, with no hidden English fallback and no missing-result misassignment.
- [x] Shared mutable translation state has one runner owner; HF workers can write only run-specific artifacts through their application code. Cancellation/orphan tests prove that a late Job cannot select or overwrite the artifact being built.
- [x] The build uses the exact source and doc-builder revisions and verifies archive identity before installation.
- [x] Existing callers and #800 HTML-cache behavior pass their regression checks.
- [x] All 29 inline review cases and review-summary follow-ups are covered or explicitly blocked with evidence; none disappear solely because the old function was deleted.
- [x] The Python lockfile and Node/runtime dependencies are verified, and syntax corpus checks run in CI without missing-prerequisite skips.
- [x] The manual doc-builder preview workflow and opt-in shared consumer are reviewable; no external repository changes, schedule changes, or production activation are included.
- [x] Ordinary translated files and a completed run README are produced from the same tree as the archive; the result exposes a Hub folder link and a translated-page link.
- [ ] When authorized, a real GPU → Bucket → HTML smoke and actual Hub click-through are recorded; until then, status says local implementation complete / live verification pending. A future production cutover remains outside this scope.
- [x] Report production Python/JS/YAML lines before/after, tests separately, and actual maintenance tradeoffs. Do not assert the original 65–80% estimate as a measured result.
- [x] Update `plans/README.md` with the completed phase and remaining live/cutover work. Mark DONE only when the agreed execution scope and required verification are fulfilled.

Stop and report the specific unresolved assumption if extraction requires a replacement Markdown engine, the parser cannot expose reliable source spans for corpus constructs, `generate_batch()` cannot safely associate/terminate results at the chosen version, the runtime cannot provide Node/CUDA together, or shared workflow publication cannot be isolated for smoke verification. Continue independent phases where useful; do not add broad fallback machinery, omit pages, or silently deploy to make a check green. A failed test calls for diagnosis and a bounded fix, not changing the expected outcome to match broken behavior.

## References

- [Translation PR and reviews](https://github.com/huggingface/doc-builder/pull/813).
- [Existing HTML cache](https://github.com/huggingface/doc-builder/pull/800).
- [Jobs API and lifecycle](https://huggingface.co/docs/huggingface_hub/main/en/guides/jobs): verify API signatures against the selected installed SDK; main documentation may describe a newer release.
- [Bucket transfers](https://huggingface.co/docs/huggingface_hub/main/en/guides/buckets): use the SDK's supported batch/upload/download functions, not filesystem atomicity assumptions.
- [Continuous batching](https://huggingface.co/docs/transformers/main/continuous_batching): verify `generate_batch()` ordering/error behavior at the pinned source.
- Source authority for Markdown: `kit/preprocessors/mdsvex/index.js`, the installed mdsvex parser, and the checked-in corpus. A parser choice does not replace the regression gate.
