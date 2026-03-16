# Runnable code blocks

This document describes runnable Python markdown fences handled by `doc-builder`.

## Authoring

`doc-builder` recognizes fenced `py` and `python` blocks tagged with `runnable` or `runnable:<label>`:

````md
```py runnable:quickstart
from transformers import pipeline
pipe = pipeline("sentiment-analysis")
print(pipe("I love this!"))
```
````

During conversion:

- the runnable annotation is removed from the fence in rendered docs
- the code content is preserved unless lines are hidden with `# nodoc`
- `# nodoc` can hide a single line or a full indented block from rendered docs

The label is used in warning messages and generated test names.

## Running runnable blocks in tests

`doc-builder` tags and transforms runnable blocks, but it does not execute them by itself.

Use the reusable helper from `hf-doc-builder`:

```python
from pathlib import Path

from doc_builder.testing import DocIntegrationTest


class MyPageDocIntegrationTest(DocIntegrationTest):
    doc_path = Path(__file__).resolve().parents[2] / "docs" / "source" / "en" / "my_page.md"
```

What it does:

- finds fenced `py`/`python` blocks marked with `runnable` or `runnable:<label>`
- creates one test per block (`runnable:my_case` becomes `test_my_case`)
- executes each block with contextual failure output, including the file path and code snippet

Run locally with:

```bash
pytest -q tests/docs/test_my_page_docs.py
```

This executes trusted documentation code with `exec`, so keep it limited to repo-controlled docs and CI.

These tests run raw markdown code blocks. If you want test behavior to match rendered docs exactly, preprocess the blocks first so `# nodoc` lines are removed before execution.

## Continuation blocks

Use `:2`, `:3`, and so on to continue a runnable block in the same namespace:

````md
```py runnable:test_basic
processor = AutoProcessor.from_pretrained("suno/bark")
inputs = processor("Hello, my dog is cute", voice_preset=voice_preset)
```

```py runnable:test_basic:2
inputs = processor("Amazing! I can speak English too.")
```
````

`runnable:test_basic:2` and later continuations are grouped with `runnable:test_basic`, so later snippets can build on earlier setup.

## Test decorators

Runnable code blocks can declare test decorators with `# pytest-decorator:` comments. The decorator is imported and applied to the generated execution function at runtime.

````md
```py runnable:test_basic
# pytest-decorator: transformers.testing_utils.slow
# pytest-decorator: transformers.testing_utils.require_torch
from transformers import pipeline
pipe = pipeline("sentiment-analysis")
print(pipe("I love this!"))
```
````

Multiple decorators on the same line are also supported:

````md
```py runnable:test_basic
# pytest-decorator: transformers.testing_utils.slow, transformers.testing_utils.require_torch
from transformers import pipeline
pipe = pipeline("sentiment-analysis")
print(pipe("I love this!"))
```
````

How it works:

- each `# pytest-decorator: <dotted.import.path>` line is parsed during collection
- the decorator is imported and applied to the code block execution function
- skip-style decorators such as `@slow` or `@require_torch` raise `unittest.SkipTest`, which pytest reports as a skip
- `# pytest-decorator:` lines are stripped from executed code and rendered documentation

## Bare-assert warnings

`doc-builder build` can emit warnings for bare `assert` statements inside runnable Python markdown fences.

This behavior is opt-in:

```bash
doc-builder build {package_name} {path_to_docs} --build_dir {build_dir} --emit-warning
```

When enabled:

- bare `assert` lines in runnable blocks emit warnings with file and line information
- `# nodoc` removes the line from rendered docs and does not warn
- `# doc-builder: ignore-bare-assert` keeps the line, silences the warning, and is removed from rendered docs

Warning formatting depends on where the build runs:

- local runs: `Warning: docs/source/en/example.md:3: ...`
- GitHub Actions: `::warning file=docs/source/en/example.md,line=3::...`

To enable this in the reusable PR workflow:

```yaml
jobs:
  build:
    uses: huggingface/doc-builder/.github/workflows/build_pr_documentation.yml@main
    with:
      # ...
      additional_args: --emit-warning
```

To fail the PR doc build on warnings:

```yaml
jobs:
  build:
    uses: huggingface/doc-builder/.github/workflows/build_pr_documentation.yml@main
    with:
      # ...
      additional_args: --emit-warning
      fail_on_warning: true
```
