# coding=utf-8
# Copyright 2021 The HuggingFace Team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import inspect
import unittest
from dataclasses import dataclass
from typing import List, Optional, Union

import timm
import transformers
from doc_builder.autodoc import (
    autodoc,
    document_object,
    find_documented_methods,
    find_object_in_package,
    format_signature,
    get_shortest_path,
    get_signature_component,
    get_source_link,
    get_type_name,
    hashlink_example_codeblock,
    is_dataclass_autodoc,
    remove_example_tags,
    resolve_links_in_text,
)
from transformers import BertModel, BertTokenizer, BertTokenizerFast
from transformers.utils import PushToHubMixin


# This is dynamic since the Transformers/timm libraries are not frozen.
TEST_LINE_NUMBER = inspect.getsourcelines(transformers.utils.ModelOutput)[1]
TEST_LINE_NUMBER2 = inspect.getsourcelines(transformers.pipeline)[1]
TEST_LINE_NUMBER_TIMM = inspect.getsourcelines(timm.create_model)[1]

TEST_DOCSTRING = """Constructs a BERTweet tokenizer, using Byte-Pair-Encoding.

This tokenizer inherits from [`~transformers.PreTrainedTokenizer`] which contains most of the main methods.
Users should refer to this superclass for more information regarding those methods.

<parameters>

- **vocab_file** (`str`) --
  Path to the vocabulary file.
- **merges_file** (`str`) --
  Path to the merges file.
- **normalization** (`bool`, _optional_, defaults to `False`) --
  Whether or not to apply a normalization preprocess.

<Tip>

When building a sequence using special tokens, this is not the token that is used for the beginning of
sequence. The token used is the `cls_token`.

</Tip>
</parameters>
<returns>

List of [input IDs](../glossary.html#input-ids) with the appropriate special tokens.

</returns>

<returntype>            `List[int]`</returntype>
<raises>
- ``ValuError`` -- this value error will be raised on wrong input type.
</raises>
<raisederrors>``ValuError``</raisederrors>
"""

TEST_DOCSTRING_WITH_EXAMPLE = """Constructs a BERTweet tokenizer, using Byte-Pair-Encoding.

This tokenizer inherits from [`~transformers.PreTrainedTokenizer`] which contains most of the main methods.
Users should refer to this superclass for more information regarding those methods.

<parameters>

- **vocab_file** (`str`) --
  Path to the vocabulary file.
- **merges_file** (`str`) --
  Path to the merges file.
- **normalization** (`bool`, _optional_, defaults to `False`) --
  Whether or not to apply a normalization preprocess.

<Tip>

When building a sequence using special tokens, this is not the token that is used for the beginning of
sequence. The token used is the `cls_token`.

</Tip>
</parameters>
<returns>

List of [input IDs](../glossary.html#input-ids) with the appropriate special tokens.

<exampletitle>Example:</exampletitle>
<example>
```python
import transformers
```
<example>

</returns>

<returntype>            `List[int]`</returntype>"""


TEST_DOCSTRING_WITH_PARAM_GROUPS = """
Builds something very cool!

<parameters>

- **param_a** (`str`) --
  First default parameter
- **param_b** (`int`) --
  Second default parameter

> New group with cool parameters!

- **cool_param_a** (`str`) --
  First cool parameter
- **cool_param_b** (`int`) --
  Second cool parameter

</parameters>
"""


class AutodocTester(unittest.TestCase):
    test_source_link = (
        f"https://github.com/huggingface/transformers/blob/main/src/transformers/utils/generic.py#L{TEST_LINE_NUMBER}"
    )
    test_source_link_init = f"https://github.com/huggingface/transformers/blob/main/src/transformers/pipelines/__init__.py#L{TEST_LINE_NUMBER2}"
    test_source_link_timm = (
        f"https://github.com/rwightman/pytorch-image-models/blob/main/timm/models/factory.py#L{TEST_LINE_NUMBER_TIMM}"
    )

    def test_find_object_in_package(self):
        self.assertEqual(find_object_in_package("BertModel", transformers), BertModel)
        self.assertEqual(find_object_in_package("transformers.BertModel", transformers), BertModel)
        self.assertEqual(find_object_in_package("models.bert.BertModel", transformers), BertModel)
        self.assertEqual(find_object_in_package("transformers.models.bert.BertModel", transformers), BertModel)
        self.assertEqual(find_object_in_package("models.bert.modeling_bert.BertModel", transformers), BertModel)
        self.assertEqual(
            find_object_in_package("transformers.models.bert.modeling_bert.BertModel", transformers), BertModel
        )

        # Works on methods too
        self.assertEqual(find_object_in_package("BertModel.forward", transformers), BertModel.forward)

        # Test with an object not in the module
        self.assertIsNone(find_object_in_package("Dataset", transformers))

    def test_remove_example_tags(self):
        text = "<example>aaa</example>bbb\n<exampletitle>ccc</exampletitle>\n\n<example>ddd</example>"
        self.assertEqual(remove_example_tags(text), "aaabbb\nccc\n\nddd")

    def test_get_shortest_path(self):
        self.assertEqual(get_shortest_path(BertModel, transformers), "transformers.BertModel")
        self.assertEqual(get_shortest_path(BertModel.forward, transformers), "transformers.BertModel.forward")
        self.assertEqual(get_shortest_path(PushToHubMixin, transformers), "transformers.utils.PushToHubMixin")

    def test_get_type_name(self):
        self.assertEqual(get_type_name(str), "str")
        self.assertEqual(get_type_name(BertModel), "BertModel")
        # Objects from typing which are the most annoying
        self.assertEqual(get_type_name(List[str]), "typing.List[str]")
        self.assertEqual(get_type_name(Optional[str]), "typing.Optional[str]")
        self.assertEqual(get_type_name(Union[bool, int]), "typing.Union[bool, int]")
        self.assertEqual(get_type_name(List[Optional[str]]), "typing.List[typing.Optional[str]]")

    def test_format_signature(self):
        self.assertEqual(
            format_signature(BertModel),
            [{"name": "config", "val": ""}, {"name": "add_pooling_layer", "val": " = True"}],
        )

        def func_with_annot(a: int = 1, b: float = 0):
            pass

        self.assertEqual(
            format_signature(func_with_annot), [{"name": "a", "val": ": int = 1"}, {"name": "b", "val": ": float = 0"}]
        )

        def generic_func(*args, **kwargs):
            pass

        self.assertEqual(
            format_signature(generic_func), [{"name": "*args", "val": ""}, {"name": "**kwargs", "val": ""}]
        )

    def test_get_signature_component(self):
        name = "class transformers.BertweetTokenizer"
        anchor = "transformers.BertweetTokenizer"
        signature = [
            {"name": "vocab_file", "val": ""},
            {"name": "normalization", "val": " = False"},
            {"name": "bos_token", "val": " = '&amp;lt;s>'"},
        ]
        object_doc = TEST_DOCSTRING
        source_link = "test_link"
        expected_signature_component = '<docstring><name>class transformers.BertweetTokenizer</name><anchor>transformers.BertweetTokenizer</anchor><source>test_link</source><parameters>[{"name": "vocab_file", "val": ""}, {"name": "normalization", "val": " = False"}, {"name": "bos_token", "val": " = \'&amp;lt;s>\'"}]</parameters><paramsdesc>- **vocab_file** (`str`) --\n  Path to the vocabulary file.\n- **merges_file** (`str`) --\n  Path to the merges file.\n- **normalization** (`bool`, _optional_, defaults to `False`) --\n  Whether or not to apply a normalization preprocess.\n\n<Tip>\n\nWhen building a sequence using special tokens, this is not the token that is used for the beginning of\nsequence. The token used is the `cls_token`.\n\n</Tip></paramsdesc><paramgroups>0</paramgroups><rettype>`List[int]`</rettype><retdesc>List of [input IDs](../glossary.html#input-ids) with the appropriate special tokens.</retdesc><raises>- ``ValuError`` -- this value error will be raised on wrong input type.</raises><raisederrors>``ValuError``</raisederrors></docstring>\nConstructs a BERTweet tokenizer, using Byte-Pair-Encoding.\n\nThis tokenizer inherits from [`~transformers.PreTrainedTokenizer`] which contains most of the main methods.\nUsers should refer to this superclass for more information regarding those methods.\n\n\n\n\n\n\n\n\n'
        self.assertEqual(
            get_signature_component(name, anchor, signature, object_doc, source_link), expected_signature_component
        )

        name = "class transformers.BertweetTokenizer"
        anchor = "transformers.BertweetTokenizer"
        signature = [
            {"name": "vocab_file", "val": ""},
            {"name": "normalization", "val": " = False"},
            {"name": "bos_token", "val": " = '&amp;lt;s>'"},
        ]
        object_doc_without_params_and_return = """Constructs a BERTweet tokenizer, using Byte-Pair-Encoding.

This tokenizer inherits from [`~transformers.PreTrainedTokenizer`] which contains most of the main methods.
Users should refer to this superclass for more information regarding those methods.
"""
        expected_signature_component = '<docstring><name>class transformers.BertweetTokenizer</name><anchor>transformers.BertweetTokenizer</anchor><source>test_link</source><parameters>[{"name": "vocab_file", "val": ""}, {"name": "normalization", "val": " = False"}, {"name": "bos_token", "val": " = \'&amp;lt;s>\'"}]</parameters></docstring>\nConstructs a BERTweet tokenizer, using Byte-Pair-Encoding.\n\nThis tokenizer inherits from [`~transformers.PreTrainedTokenizer`] which contains most of the main methods.\nUsers should refer to this superclass for more information regarding those methods.\n\n'
        self.assertEqual(
            get_signature_component(name, anchor, signature, object_doc_without_params_and_return, source_link),
            expected_signature_component,
        )

        name = "class transformers.cool_function"
        anchor = "transformers.cool_function"
        signature = [
            {"name": "param_a", "val": ""},
            {"name": "param_b", "val": ""},
            {"name": "cool_param_a", "val": ""},
            {"name": "cool_param_b", "val": ""},
        ]
        object_doc = TEST_DOCSTRING_WITH_PARAM_GROUPS
        source_link = "test_link"
        expected_signature_component = '<docstring><name>class transformers.cool_function</name><anchor>transformers.cool_function</anchor><source>test_link</source><parameters>[{"name": "param_a", "val": ""}, {"name": "param_b", "val": ""}, {"name": "cool_param_a", "val": ""}, {"name": "cool_param_b", "val": ""}]</parameters><paramsdesc>- **param_a** (`str`) --\n  First default parameter\n- **param_b** (`int`) --\n  Second default parameter\n\n</paramsdesc><paramsdesc1title>New group with cool parameters!</paramsdesc1title><paramsdesc1>\n\n- **cool_param_a** (`str`) --\n  First cool parameter\n- **cool_param_b** (`int`) --\n  Second cool parameter</paramsdesc1><paramgroups>1</paramgroups></docstring>\n\nBuilds something very cool!\n\n\n\n'
        self.assertEqual(
            get_signature_component(name, anchor, signature, object_doc, source_link), expected_signature_component
        )

    def test_get_source_link(self):
        page_info = {"package_name": "transformers"}
        self.assertEqual(get_source_link(transformers.utils.ModelOutput, page_info), self.test_source_link)
        self.assertEqual(get_source_link(transformers.pipeline, page_info), self.test_source_link_init)

    def test_get_source_link_different_repo_owner(self):
        page_info = {"package_name": "timm", "repo_owner": "rwightman", "repo_name": "pytorch-image-models"}
        self.assertEqual(
            get_source_link(timm.create_model, page_info, version_tag_suffix=""), self.test_source_link_timm
        )

    def test_document_object(self):
        page_info = {"package_name": "transformers"}

        model_output_doc = """
<docstring><name>class transformers.utils.ModelOutput</name><anchor>transformers.utils.ModelOutput</anchor><source>"""
        model_output_doc += f"{self.test_source_link}"
        model_output_doc += """</source><parameters>""</parameters></docstring>

Base class for all model outputs as dataclass. Has a `__getitem__` that allows indexing by integer or slice (like a
tuple) or strings (like a dictionary) that will ignore the `None` attributes. Otherwise behaves like a regular
python dictionary.

<Tip warning={true}>

You can't unpack a `ModelOutput` directly. Use the [`~utils.ModelOutput.to_tuple`] method to convert it to a tuple
before.

</Tip>


"""
        self.assertEqual(document_object("utils.ModelOutput", transformers, page_info)[0], model_output_doc)

    def test_find_document_methods(self):
        self.assertListEqual(find_documented_methods(BertModel), ["forward"])
        self.assertListEqual(
            find_documented_methods(BertTokenizer),
            [
                "build_inputs_with_special_tokens",
                "convert_tokens_to_string",
                "create_token_type_ids_from_sequences",
                "get_special_tokens_mask",
            ],
        )
        self.assertListEqual(
            find_documented_methods(BertTokenizerFast),
            ["build_inputs_with_special_tokens", "create_token_type_ids_from_sequences"],
        )

    def test_autodoc_return_anchors(self):
        _, anchors, _ = autodoc("BertTokenizer", transformers, return_anchors=True)
        self.assertListEqual(
            anchors,
            [
                "transformers.BertTokenizer",
                "transformers.BertTokenizer.build_inputs_with_special_tokens",
                "transformers.BertTokenizer.convert_tokens_to_string",
                "transformers.BertTokenizer.create_token_type_ids_from_sequences",
                "transformers.BertTokenizer.get_special_tokens_mask",
            ],
        )

        _, anchors, _ = autodoc("BertTokenizer", transformers, methods=["__call__", "all"], return_anchors=True)
        self.assertListEqual(
            anchors,
            [
                "transformers.BertTokenizer",
                ("transformers.BertTokenizer.__call__", "transformers.PreTrainedTokenizerBase.__call__"),
                "transformers.BertTokenizer.build_inputs_with_special_tokens",
                "transformers.BertTokenizer.convert_tokens_to_string",
                "transformers.BertTokenizer.create_token_type_ids_from_sequences",
                "transformers.BertTokenizer.get_special_tokens_mask",
            ],
        )

        _, anchors, _ = autodoc("BertTokenizer", transformers, methods=["__call__"], return_anchors=True)
        self.assertListEqual(
            anchors,
            [
                "transformers.BertTokenizer",
                ("transformers.BertTokenizer.__call__", "transformers.PreTrainedTokenizerBase.__call__"),
            ],
        )

    def test_resolve_links_in_text(self):
        page_info = {"package_name": "transformers"}
        small_mapping = {
            "transformers.BertModel": "model_doc/bert.html",
            "transformers.BertModel.forward": "model_doc/bert.html",
            "transformers.BertTokenizer": "bert.html",
        }

        self.maxDiff = None
        self.assertEqual(
            resolve_links_in_text(
                "Link to [`BertModel`], [`BertModel.forward`] and [`BertTokenizer`] as well as [`SomeClass`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [BertModel](/docs/transformers/main/en/model_doc/bert.html#transformers.BertModel), "
                "[BertModel.forward()](/docs/transformers/main/en/model_doc/bert.html#transformers.BertModel.forward) "
                "and [BertTokenizer](/docs/transformers/main/en/bert.html#transformers.BertTokenizer) as well as `SomeClass`."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`~transformers.BertModel`], [`~transformers.BertModel.forward`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [BertModel](/docs/transformers/main/en/model_doc/bert.html#transformers.BertModel), "
                "[forward()](/docs/transformers/main/en/model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`transformers.BertModel`], [`transformers.BertModel.forward`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [transformers.BertModel](/docs/transformers/main/en/model_doc/bert.html#transformers.BertModel), "
                "[transformers.BertModel.forward()](/docs/transformers/main/en/model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`transformers.BertModel.forward#input_ids`], [`~transformers.BertModel.forward#input_ids`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [input_ids](/docs/transformers/main/en/model_doc/bert.html#transformers.BertModel.forward.input_ids), [input_ids](/docs/transformers/main/en/model_doc/bert.html#transformers.BertModel.forward.input_ids)."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "This is a regular [`link`](url)",
                transformers,
                small_mapping,
                page_info,
            ),
            "This is a regular [`link`](url)",
        )

    def test_resolve_links_in_text_custom_version_lang(self):
        page_info = {"package_name": "transformers", "version": "v4.10.0", "language": "fr"}
        small_mapping = {
            "transformers.BertModel": "model_doc/bert.html",
            "transformers.BertModel.forward": "model_doc/bert.html",
            "transformers.BertTokenizer": "bert.html",
        }

        self.maxDiff = None
        self.assertEqual(
            resolve_links_in_text(
                "Link to [`BertModel`], [`BertModel.forward`] and [`BertTokenizer`] as well as [`SomeClass`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [BertModel](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel), "
                "[BertModel.forward()](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel.forward) "
                "and [BertTokenizer](/docs/transformers/v4.10.0/fr/bert.html#transformers.BertTokenizer) as well as `SomeClass`."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`~transformers.BertModel`], [`~transformers.BertModel.forward`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [BertModel](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel), "
                "[forward()](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

        self.assertEqual(
            resolve_links_in_text(
                "Link to [`transformers.BertModel`], [`transformers.BertModel.forward`].",
                transformers,
                small_mapping,
                page_info,
            ),
            (
                "Link to [transformers.BertModel](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel), "
                "[transformers.BertModel.forward()](/docs/transformers/v4.10.0/fr/model_doc/bert.html#transformers.BertModel.forward)."
            ),
        )

    def test_is_dataclass_autodoc(self):
        # example auto generated doc from dataclass
        @dataclass(frozen=True)
        class MyClass:
            attr1: str = "audio_file_path"
            attr2: str = "transcription"

        self.assertEqual(MyClass.__doc__, "MyClass(attr1: str = 'audio_file_path', attr2: str = 'transcription')")

        # test data class auto generated doc
        @dataclass(frozen=True)
        class AutomaticSpeechRecognition:
            audio_file_path_column: str = "audio_file_path"
            transcription_column: str = "transcription"

        self.assertTrue(is_dataclass_autodoc(AutomaticSpeechRecognition))

        # test data class auto non-generated doc
        @dataclass(frozen=True)
        class AutomaticSpeechRecognition:
            """
            Non auto generated doc
            """

            audio_file_path_column: str = "audio_file_path"
            transcription_column: str = "transcription"

        self.assertFalse(is_dataclass_autodoc(AutomaticSpeechRecognition))

        # test class with no signature (because of `dict` inheritance)
        class AutomaticSpeechRecognition(dict):
            audio_file_path_column: str = "audio_file_path"
            transcription_column: str = "transcription"

        self.assertFalse(is_dataclass_autodoc(AutomaticSpeechRecognition))

    def test_resolve_links_in_text_other_docs(self):
        page_info = {"package_name": "transformers", "version": "main", "language": "en"}
        self.assertEqual(
            resolve_links_in_text(
                "Link to [`~accelerate.Accelerator`], [`~accelerate.Accelerator.prepare`].",
                transformers,
                {},
                page_info,
            ),
            (
                "Link to [Accelerator](https://huggingface.co/docs/accelerate/main/en/package_reference/accelerator#accelerate.Accelerator), "
                "[prepare](https://huggingface.co/docs/accelerate/main/en/package_reference/accelerator#accelerate.Accelerator.prepare)."
            ),
        )
        self.assertEqual(
            resolve_links_in_text(
                "Link to [`datasets.Dataset`].",
                transformers,
                {},
                page_info,
            ),
            (
                "Link to [datasets.Dataset](https://huggingface.co/docs/datasets/main/en/package_reference/main_classes#datasets.Dataset)."
            ),
        )

    def test_autodoc_getset_descriptor(self):
        import tokenizers

        documentation = autodoc("AddedToken.content", tokenizers, return_anchors=False)
        expected_documentation = """<div class="docstring border-l-2 border-t-2 pl-4 pt-3.5 border-gray-100 rounded-tl-xl mb-6 mt-8">

<docstring><name>content</name><anchor>None</anchor><parameters>[]</parameters><isgetsetdescriptor></docstring>
Get the content of this `AddedToken`

</div>\n"""
        self.assertEqual(documentation, expected_documentation)

    def test_hashlink_example_codeblock(self):
        dummy_anchor = "myfunc"
        # test canonical
        original_md = """Example:
```python
import numpy as np
```"""
        expected_conversion = """<ExampleCodeBlock anchor="myfunc.example">

Example:
```python
import numpy as np
```

</ExampleCodeBlock>"""
        self.assertEqual(hashlink_example_codeblock(original_md, dummy_anchor), expected_conversion)

        # test `Examples` ending in `s`
        original_md = """Examples:
```python
import numpy as np
```"""
        expected_conversion = """<ExampleCodeBlock anchor="myfunc.example">

Examples:
```python
import numpy as np
```

</ExampleCodeBlock>"""
        self.assertEqual(hashlink_example_codeblock(original_md, dummy_anchor), expected_conversion)

        # test part of bigger doc description
        original_md = """Some description about this function
Example:
```python
import numpy as np
```"""
        expected_conversion = """Some description about this function
<ExampleCodeBlock anchor="myfunc.example">

Example:
```python
import numpy as np
```

</ExampleCodeBlock>"""
        self.assertEqual(hashlink_example_codeblock(original_md, dummy_anchor), expected_conversion)

        # test complex example introduction
        original_md = """Here is a classification example:
```python
import numpy as np
```"""
        expected_conversion = """<ExampleCodeBlock anchor="myfunc.example">

Here is a classification example:
```python
import numpy as np
```

</ExampleCodeBlock>"""
        self.assertEqual(hashlink_example_codeblock(original_md, dummy_anchor), expected_conversion)

        # test doc description with multiple examples
        original_md = """Here is a classification example:
```python
import numpy as np
```

Here is a regression example:
```python
import scipy as sp
```"""
        expected_conversion = """<ExampleCodeBlock anchor="myfunc.example">

Here is a classification example:
```python
import numpy as np
```

</ExampleCodeBlock>

<ExampleCodeBlock anchor="myfunc.example-2">

Here is a regression example:
```python
import scipy as sp
```

</ExampleCodeBlock>"""
        self.assertEqual(hashlink_example_codeblock(original_md, dummy_anchor), expected_conversion)

        # test example with inline ``` (inline ``` should be escaped)
        original_md = """The tokenization method is `<tokens> <eos> <language code>` for source language documents, and ```<language code>
<tokens> <eos>``` for target language documents.

Examples:

```python
>>> from transformers import MBartTokenizer

>>> tokenizer = MBartTokenizer.from_pretrained("facebook/mbart-large-en-ro", src_lang="en_XX", tgt_lang="ro_RO")
>>> example_english_phrase = " UN Chief Says There Is No Military Solution in Syria"
>>> expected_translation_romanian = "Şeful ONU declară că nu există o soluţie militară în Siria"
>>> inputs = tokenizer(example_english_phrase, return_tensors="pt")
>>> with tokenizer.as_target_tokenizer():
...     labels = tokenizer(expected_translation_romanian, return_tensors="pt")
>>> inputs["labels"] = labels["input_ids"]
```"""
        expected_conversion = """The tokenization method is `<tokens> <eos> <language code>` for source language documents, and ```<language code>
<tokens> <eos>``` for target language documents.

<ExampleCodeBlock anchor="myfunc.example">

Examples:

```python
>>> from transformers import MBartTokenizer

>>> tokenizer = MBartTokenizer.from_pretrained("facebook/mbart-large-en-ro", src_lang="en_XX", tgt_lang="ro_RO")
>>> example_english_phrase = " UN Chief Says There Is No Military Solution in Syria"
>>> expected_translation_romanian = "Şeful ONU declară că nu există o soluţie militară în Siria"
>>> inputs = tokenizer(example_english_phrase, return_tensors="pt")
>>> with tokenizer.as_target_tokenizer():
...     labels = tokenizer(expected_translation_romanian, return_tensors="pt")
>>> inputs["labels"] = labels["input_ids"]
```

</ExampleCodeBlock>"""
        self.assertEqual(hashlink_example_codeblock(original_md, dummy_anchor), expected_conversion)

        # test indentation (there should be no indendetation)
        original_md = """Some example with indentation
        ```
        some pythong
        ```
        """
        self.assertEqual(hashlink_example_codeblock(original_md, dummy_anchor), original_md)
