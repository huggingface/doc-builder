# Copyright 2026 The HuggingFace Team. All rights reserved.
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

"""
Translates a library's English docs into another language, remembering what it has already
done so it only pays for what changed.

    doc-builder translate transformers --lang ja --bucket /bucket

Running it needs `torch` and `transformers`, so they live behind the `translate` extra rather
than being installed for everyone. Only the function that actually calls the model imports
them, and it does so at the last moment -- so everything else here, including the whole test
suite, runs without them.

Start with `segment.py`. Hiding the parts of a page that must not be translated is the idea
the rest of this is built on.
"""
