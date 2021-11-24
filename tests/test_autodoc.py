import sys
import inspect
import unittest

import transformers

from typing import List, Optional, Union
from transformers import BertModel, BertTokenizer, BertTokenizerFast
from transformers.file_utils import PushToHubMixin

# To find the doc_builder package.
sys.path.append("src")

from doc_builder.autodoc import (
    autodoc,
    document_object,
    find_documented_methods,
    find_object_in_package,
    format_signature,
    get_signature_component,
    get_source_link,
    get_shortest_path,
    get_type_name,
    remove_example_tags,
)


# This is dynamic since the Transformers library is not frozen.
TEST_LINE_NUMBER = inspect.getsourcelines(transformers.file_utils.ModelOutput)[1]

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

<returntype>            `List[int]`</returntype>"""

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
    test_source_link = f"https://github.com/huggingface/transformers/blob/master/src/transformers/file_utils.py#L{TEST_LINE_NUMBER}"

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
        text = '<example>aaa</example>bbb\n<exampletitle>ccc</exampletitle>\n\n<example>ddd</example>'
        self.assertEqual(remove_example_tags(text), 'aaabbb\nccc\n\nddd')

    def test_get_shortest_path(self):
        self.assertEqual(get_shortest_path(BertModel, transformers), "transformers.BertModel")
        self.assertEqual(get_shortest_path(BertModel.forward, transformers), "transformers.BertModel.forward")
        self.assertEqual(get_shortest_path(PushToHubMixin, transformers), "transformers.file_utils.PushToHubMixin")

    def test_get_type_name(self):
        self.assertEqual(get_type_name(str), "str")
        self.assertEqual(get_type_name(BertModel), "BertModel")
        # Objects from typing which are the most annoying
        self.assertEqual(get_type_name(List[str]), "typing.List[str]")
        self.assertEqual(get_type_name(Optional[str]), "typing.Optional[str]")
        self.assertEqual(get_type_name(Union[bool, int]), "typing.Union[bool, int]")
        self.assertEqual(get_type_name(List[Optional[str]]), "typing.List[typing.Optional[str]]")
    
    def test_format_signature(self):
        self.assertEqual(format_signature(BertModel), [{'name': 'config', 'val': ''}, {'name': 'add_pooling_layer', 'val': ' = True'}])

        def func_with_annot(a: int = 1, b: float = 0): pass
        self.assertEqual(format_signature(func_with_annot), [{'name': 'a', 'val': ': int = 1'}, {'name': 'b', 'val': ': float = 0'}])

        def generic_func(*args, **kwargs): pass
        self.assertEqual(format_signature(generic_func), [{'name': '*args', 'val': ''}, {'name': '**kwargs', 'val': ''}])

    def test_get_signature_component(self):
        name = "class transformers.BertweetTokenizer"
        anchor = "transformers.BertweetTokenizer"
        signature = [
            {'name': 'vocab_file', 'val': ''}, 
            {'name': 'normalization', 'val': ' = False'}, 
            {'name': 'bos_token', 'val': " = '&amp;lt;s>'"},
        ]
        object_doc = TEST_DOCSTRING
        source_link = "test_link"
        expected_signature_component = '<docstring><name>class transformers.BertweetTokenizer</name><anchor>transformers.BertweetTokenizer</anchor><source>test_link</source><parameters>[{"name": "vocab_file", "val": ""}, {"name": "normalization", "val": " = False"}, {"name": "bos_token", "val": " = \'&amp;lt;s>\'"}]</parameters><paramsdesc>- **vocab_file** (`str`) --\n  Path to the vocabulary file.\n- **merges_file** (`str`) --\n  Path to the merges file.\n- **normalization** (`bool`, _optional_, defaults to `False`) --\n  Whether or not to apply a normalization preprocess.\n\n<Tip>\n\nWhen building a sequence using special tokens, this is not the token that is used for the beginning of\nsequence. The token used is the `cls_token`.\n\n</Tip></paramsdesc><paramgroups>0</paramgroups><rettype>`List[int]`</rettype><retdesc>List of [input IDs](../glossary.html#input-ids) with the appropriate special tokens.</retdesc></docstring>\nConstructs a BERTweet tokenizer, using Byte-Pair-Encoding.\n\nThis tokenizer inherits from [`~transformers.PreTrainedTokenizer`] which contains most of the main methods.\nUsers should refer to this superclass for more information regarding those methods.\n\n\n\n\n\n'
        self.assertEqual(get_signature_component(name, anchor, signature, object_doc, source_link), expected_signature_component)

        name = "class transformers.BertweetTokenizer"
        anchor = "transformers.BertweetTokenizer"
        signature = [
            {'name': 'vocab_file', 'val': ''}, 
            {'name': 'normalization', 'val': ' = False'}, 
            {'name': 'bos_token', 'val': " = '&amp;lt;s>'"},
        ]
        object_doc_without_params_and_return = """Constructs a BERTweet tokenizer, using Byte-Pair-Encoding.

This tokenizer inherits from [`~transformers.PreTrainedTokenizer`] which contains most of the main methods.
Users should refer to this superclass for more information regarding those methods.
"""
        expected_signature_component = '<docstring><name>class transformers.BertweetTokenizer</name><anchor>transformers.BertweetTokenizer</anchor><source>test_link</source><parameters>[{"name": "vocab_file", "val": ""}, {"name": "normalization", "val": " = False"}, {"name": "bos_token", "val": " = \'&amp;lt;s>\'"}]</parameters></docstring>\nConstructs a BERTweet tokenizer, using Byte-Pair-Encoding.\n\nThis tokenizer inherits from [`~transformers.PreTrainedTokenizer`] which contains most of the main methods.\nUsers should refer to this superclass for more information regarding those methods.\n\n'
        self.assertEqual(get_signature_component(name, anchor, signature, object_doc_without_params_and_return, source_link), expected_signature_component)

        name = "class transformers.cool_function"
        anchor = "transformers.cool_function"
        signature = [
            {'name': 'param_a', 'val': ''},
            {'name': 'param_b', 'val': ''},
            {'name': 'cool_param_a', 'val': ''},
            {'name': 'cool_param_b', 'val': ''},
        ]
        object_doc = TEST_DOCSTRING_WITH_PARAM_GROUPS
        source_link = "test_link"
        expected_signature_component = '<docstring><name>class transformers.cool_function</name><anchor>transformers.cool_function</anchor><source>test_link</source><parameters>[{"name": "param_a", "val": ""}, {"name": "param_b", "val": ""}, {"name": "cool_param_a", "val": ""}, {"name": "cool_param_b", "val": ""}]</parameters><paramsdesc>- **param_a** (`str`) --\n  First default parameter\n- **param_b** (`int`) --\n  Second default parameter\n\n</paramsdesc><paramsdesc1title>New group with cool parameters!</paramsdesc1title><paramsdesc1>\n\n- **cool_param_a** (`str`) --\n  First cool parameter\n- **cool_param_b** (`int`) --\n  Second cool parameter</paramsdesc1><paramgroups>1</paramgroups></docstring>\n\nBuilds something very cool!\n\n\n\n'
        self.assertEqual(get_signature_component(name, anchor, signature, object_doc, source_link), expected_signature_component)

    def test_get_source_link(self):
        page_info = {"package_name": "transformers"}
        self.assertEqual(get_source_link(transformers.file_utils.ModelOutput, page_info), self.test_source_link)

    def test_document_object(self):
        page_info = {"package_name": "transformers"}

        model_output_doc = """
<docstring><name>class transformers.file\_utils.ModelOutput</name><anchor>transformers.file_utils.ModelOutput</anchor><source>"""
        model_output_doc += f'{self.test_source_link}'
        model_output_doc += """</source><parameters>""</parameters></docstring>

Base class for all model outputs as dataclass. Has a `__getitem__` that allows indexing by integer or slice (like
a tuple) or strings (like a dictionary) that will ignore the `None` attributes. Otherwise behaves like a regular
python dictionary.

<Tip warning={true}>

You can't unpack a `ModelOutput` directly. Use the [`~transformers.file_utils.ModelOutput.to_tuple`]
method to convert it to a tuple before.

</Tip>


"""
        self.assertEqual(document_object("file_utils.ModelOutput", transformers, page_info), model_output_doc)

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
        _, anchors = autodoc("BertTokenizer", transformers, return_anchors=True)
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

        _, anchors = autodoc("BertTokenizer", transformers, methods=["__call__", "all"], return_anchors=True)
        self.assertListEqual(
            anchors,
            [
                "transformers.BertTokenizer",
                "transformers.BertTokenizer.__call__",
                "transformers.BertTokenizer.build_inputs_with_special_tokens",
                "transformers.BertTokenizer.convert_tokens_to_string",
                "transformers.BertTokenizer.create_token_type_ids_from_sequences",
                "transformers.BertTokenizer.get_special_tokens_mask",
            ],
        )

        _, anchors = autodoc("BertTokenizer", transformers, methods=["__call__"], return_anchors=True)
        self.assertListEqual(anchors, ["transformers.BertTokenizer", "transformers.BertTokenizer.__call__"])
