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

import unittest

from doc_builder.commands.convert_doc_file import shorten_internal_refs


class ConvertDocFileTester(unittest.TestCase):
    def test_shorten_internal_refs(self):
        self.assertEqual(shorten_internal_refs("Checkout the [`~transformers.Trainer`]."), "Checkout the [`Trainer`].")
        self.assertEqual(
            shorten_internal_refs("Look at the [`~transformers.PreTrainedModel.generate`] method."),
            "Look at the [`~PreTrainedModel.generate`] method.",
        )
