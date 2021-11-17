import sys
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
    get_shortest_path,
    get_type_name,
)


class AutodocTester(unittest.TestCase):
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
        self.assertEqual(format_signature(BertModel), "config, add_pooling_layer = True")

        def func_with_annot(a: int = 1, b: float = 0): pass
        self.assertEqual(format_signature(func_with_annot), "a: int = 1, b: float = 0")

        def generic_func(*args, **kwargs): pass
        self.assertEqual(format_signature(generic_func), "*args, **kwargs")
    
    def test_document_object(self):
        page_info = {"package_name": "transformers"}
        # Might need some tweaking if the documentation of those objects change.
        self.assertEqual(
            document_object("is_torch_available", transformers, page_info),
            "<a id='transformers.is_torch_available'></a>\n> **transformers.is\\_torch\\_available**()\n"
        )

        model_output_doc = """<a id='transformers.file_utils.ModelOutput'></a>
> **class transformers.file\_utils.ModelOutput**()


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
