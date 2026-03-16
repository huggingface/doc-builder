# Runnable code blocks

This document describes runnable Python markdown fences handled by `doc-builder`.

## Authoring

`doc-builder` recognizes fenced `py` and `python` blocks tagged with `runnable` or `runnable:<label>`:

````md
```py runnable:quickstart
import torch
from transformers import AutoProcessor, GlmAsrForConditionalGeneration

checkpoint_name = "zai-org/GLM-ASR-Nano-2512"
audio_url = "https://huggingface.co/datasets/eustlb/audio-samples/resolve/main/bcn_weather.mp3"

processor = AutoProcessor.from_pretrained(checkpoint_name)
model = GlmAsrForConditionalGeneration.from_pretrained(checkpoint_name, device_map="auto", dtype="auto")

conversation = [
    [
        {
            "role": "user",
            "content": [
                {"type": "audio", "url": audio_url},
                {"type": "text", "text": "Please transcribe this audio into text"},
            ],
        }
    ]
]

inputs = processor.apply_chat_template(
    conversation, tokenize=True, add_generation_prompt=True, return_dict=True
).to(model.device, dtype=model.dtype)

inputs_transcription = processor.apply_transcription_request([audio_url]).to(model.device, dtype=model.dtype)

for key in inputs:  # doc-builder: hide
    assert torch.equal(inputs[key], inputs_transcription[key])

outputs = model.generate(**inputs, do_sample=False, max_new_tokens=128)
decoded_outputs = processor.batch_decode(outputs[:, inputs.input_ids.shape[1] :], skip_special_tokens=True)

print(decoded_outputs)
assert decoded_outputs == [
    "Yesterday it was thirty five degrees in Barcelona, but today the temperature will go down to minus twenty degrees."
]  # doc-builder: ignore-bare-assert
```
````

During conversion:

- the runnable annotation is removed from the fence in rendered docs
- the code content is preserved unless lines are hidden with `# doc-builder: hide`
- `# doc-builder: hide` can hide a single line or a full indented block from rendered docs
- `# doc-builder: ignore-bare-assert` keeps a bare `assert` in the block while suppressing the bare-assert warning for that line
- the `# doc-builder: ignore-bare-assert` directive is removed from rendered docs

The label is used in warning messages and generated test names.

## Running runnable blocks in tests

When `hf-doc-builder` is installed, pytest auto-loads the `doc-builder` plugin. This makes running runnable blocks against `.md` files a supported workflow, and it is the recommended way to execute them in most projects.

You can point pytest directly at a markdown page:

```bash
pytest -q docs/source/en/my_page.md
```

Or at a directory of markdown docs:

```bash
pytest -q docs/source/en/
```

What the pytest plugin does:

- collects runnable blocks from the `.md` files passed to pytest
- finds fenced `py`/`python` blocks marked with `runnable` or `runnable:<label>`
- groups continuation blocks such as `runnable:test_basic:2` with the earlier block
- creates one pytest item per runnable block
- applies `# pytest-decorator:` directives before execution
- reports failures with the markdown file path and runnable code snippet

`DocIntegrationTest` is a lower-level helper. It is not required for markdown-based doc tests. Use it only if you want to manage doc execution from regular Python test files in your project, or if you need tighter control over the Python-side test wrapper.

Example:

```python
from pathlib import Path

from doc_builder.testing import DocIntegrationTest


class MyPageDocIntegrationTest(DocIntegrationTest):
    doc_path = Path(__file__).resolve().parents[2] / "docs" / "source" / "en" / "my_page.md"
```

`DocIntegrationTest` reads one markdown file, creates one Python test per runnable block (`runnable:my_case` becomes `test_my_case`), and executes those blocks from a standard pytest test module.

Run locally with:

```bash
pytest -q tests/docs/test_my_page_docs.py
```

Both approaches execute trusted documentation code with `exec`, so keep them limited to repo-controlled docs and CI.

Both approaches run raw markdown code blocks. If you want test behavior to match rendered docs exactly, preprocess the blocks first so `# doc-builder: hide` lines are removed before execution.

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
- `# doc-builder: hide` removes the line from rendered docs and does not warn
- `# doc-builder: ignore-bare-assert` keeps the line, silences the warning, and is removed from rendered docs

Warning formatting depends on where the build runs:

- local runs: `Warning: docs/source/en/example.md:3: ...`
- GitHub Actions: `::warning file=docs/source/en/example.md,line=3::...`

## GitHub pipeline integration

If you use the reusable PR documentation workflow, pass `--emit-warning` through `additional_args`:

```yaml
jobs:
  build:
    uses: huggingface/doc-builder/.github/workflows/build_pr_documentation.yml@main
    with:
      # ...
      additional_args: --emit-warning
```

To fail the PR documentation build on warnings, also set `fail_on_warning: true`:

```yaml
jobs:
  build:
    uses: huggingface/doc-builder/.github/workflows/build_pr_documentation.yml@main
    with:
      # ...
      additional_args: --emit-warning
      fail_on_warning: true
```
