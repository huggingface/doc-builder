import pytest

from doc_builder.convert_md_to_mdx import clean_runnable_blocks, process_md
from doc_builder.runnable_params import (
    bind_runnable_code,
    parameter_cases,
    parse_fence_attributes,
    parse_runnable_frontmatter,
    strip_runnable_frontmatter,
)
from doc_builder.testing import DocIntegrationTest

pytest_plugins = ["pytester"]

SNIPPET = """from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "HuggingFaceTB/SmolLM-135M"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(model_id).to("cpu")  # a comment survives
"""

PAGE = """---
runnable:
  checkpoints:
    - HuggingFaceTB/SmolLM-135M
    - HuggingFaceTB/SmolLM-360M
  load_kwargs:
    default: {}
    eager: {attn_implementation: eager}
---

# SmolLM

```py runnable:generate checkpoints="model_id" load_kwargs="model"
model_id = "HuggingFaceTB/SmolLM-135M"
model = dict(model_id=model_id)  # doc-builder: hide
```
"""


def test_fence_attributes_quoted_or_not():
    assert parse_fence_attributes(' runnable:generate checkpoints="model_id" load_kwargs=model') == {
        "checkpoints": "model_id",
        "load_kwargs": "model",
    }
    assert parse_fence_attributes(" runnable:generate") == {}


def test_collector_keeps_label_and_attributes():
    (block,) = DocIntegrationTest._collect_runnable_blocks_from_text(PAGE)
    assert block.name == "generate"
    assert block.attributes == {"checkpoints": "model_id", "load_kwargs": "model"}


def test_bind_swaps_checkpoint_and_adds_load_kwargs_only_to_the_model():
    attributes = {"checkpoints": "model_id", "load_kwargs": "model"}
    bound = bind_runnable_code(SNIPPET, attributes, checkpoint="/tmp/fixture", load_kwargs={"dtype": "bfloat16"})
    assert bound == SNIPPET.replace('"HuggingFaceTB/SmolLM-135M"', "'/tmp/fixture'").replace(
        "from_pretrained(model_id).to", "from_pretrained(model_id, dtype='bfloat16').to"
    )


def test_bind_with_no_values_is_identity():
    assert bind_runnable_code(SNIPPET, {"checkpoints": "model_id"}) == SNIPPET


def test_bind_overrides_a_kwarg_the_snippet_already_passes():
    code = 'model = Auto.from_pretrained(\n    model_id,\n    dtype="auto",\n)\n'
    bound = bind_runnable_code(
        code, {"load_kwargs": "model"}, load_kwargs={"dtype": "float32", "attn_implementation": "eager"}
    )
    assert (
        bound == "model = Auto.from_pretrained(\n    model_id,\n    dtype='float32', attn_implementation='eager',\n)\n"
    )


def test_bind_fails_loudly_on_a_name_with_nothing_to_bind():
    with pytest.raises(ValueError, match="checkpoints='repo'"):
        bind_runnable_code(SNIPPET, {"checkpoints": "repo"}, checkpoint="x")
    with pytest.raises(ValueError, match="load_kwargs='tokenizer2'"):
        bind_runnable_code(SNIPPET, {"load_kwargs": "tokenizer2"}, load_kwargs={"dtype": "x"})


def test_parameter_cases_are_the_product():
    frontmatter = parse_runnable_frontmatter(PAGE)
    cases = parameter_cases({"checkpoints": "model_id", "load_kwargs": "model"}, frontmatter)
    assert [c[0] for c in cases] == [
        "SmolLM-135M-default",
        "SmolLM-135M-eager",
        "SmolLM-360M-default",
        "SmolLM-360M-eager",
    ]
    assert parameter_cases({}, frontmatter) == []
    assert [c[0] for c in parameter_cases({"load_kwargs": "model"}, frontmatter)] == ["default", "eager"]


def test_rendered_page_is_unchanged_by_parameters():
    plain = '# SmolLM\n\n```py runnable:generate\nmodel_id = "HuggingFaceTB/SmolLM-135M"\nmodel = dict(model_id=model_id)  # doc-builder: hide\n```\n'
    page_info = {"package_name": "transformers", "version": "main", "language": "en"}
    assert process_md(PAGE, page_info) == process_md(plain, page_info)
    assert "```py\nmodel_id" in clean_runnable_blocks(PAGE)


def test_other_frontmatter_keys_are_kept():
    page = "---\ntitle: SmolLM\nrunnable:\n  checkpoints: [a/b]\nlocal: true\n---\n# SmolLM\n"
    assert strip_runnable_frontmatter(page) == "---\ntitle: SmolLM\nlocal: true\n---\n# SmolLM\n"
    assert strip_runnable_frontmatter("# no frontmatter\n") == "# no frontmatter\n"


def test_pytest_plugin_runs_one_item_per_case(pytester):
    pytester.makefile(
        ".md",
        page="""---
runnable:
  checkpoints: [org/first, org/second]
  load_kwargs:
    default: {}
    eager: {attn_implementation: eager}
---

```py runnable:load checkpoints="model_id" load_kwargs="model"
class Auto:
    @staticmethod
    def from_pretrained(name, **kwargs):
        return name, kwargs

model_id = "org/first"
model = Auto.from_pretrained(model_id)
print(model)
```

```py runnable:plain
x = 1
```
""",
    )
    result = pytester.runpytest("-v", "-s", "page.md")
    result.assert_outcomes(passed=5)
    result.stdout.fnmatch_lines(["*load?second-eager?*"])
    result.stdout.fnmatch_lines(["*('org/second', {'attn_implementation': 'eager'})*"])
