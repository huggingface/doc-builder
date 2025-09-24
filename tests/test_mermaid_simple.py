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


import re
import unittest

from doc_builder.convert_md_to_mdx import convert_md_to_mdx


class MermaidTester(unittest.TestCase):
    def test_mermaid_detection_in_markdown(self):
        """Test that mermaid code blocks are properly detected in markdown content"""

        # Test markdown content with mermaid diagrams
        test_content = """# Test Document

Here is a mermaid diagram:

```mermaid
graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[End]
    D --> E
```

And some regular code:

```python
print('Hello World')
```

Another mermaid:

```mermaid
sequenceDiagram
    Alice->>Bob: Hello Bob, how are you?
    Bob-->>Alice: Great!
```
"""

        # Check that mermaid code blocks are present
        mermaid_blocks = re.findall(r"```mermaid\n(.*?)\n```", test_content, re.DOTALL)
        self.assertGreater(len(mermaid_blocks), 0, "Should find at least one mermaid code block")
        self.assertEqual(len(mermaid_blocks), 2, "Should find exactly 2 mermaid code blocks")

        # Check that regular code blocks are also present
        python_blocks = re.findall(r"```python\n(.*?)\n```", test_content, re.DOTALL)
        self.assertGreater(len(python_blocks), 0, "Should find at least one python code block")
        self.assertEqual(len(python_blocks), 1, "Should find exactly 1 python code block")

        # Verify the content of the first mermaid block
        first_mermaid = mermaid_blocks[0].strip()
        self.assertIn("graph TD", first_mermaid, "First mermaid block should contain 'graph TD'")
        self.assertIn("A[Start]", first_mermaid, "First mermaid block should contain 'A[Start]'")

        # Verify the content of the second mermaid block
        second_mermaid = mermaid_blocks[1].strip()
        self.assertIn("sequenceDiagram", second_mermaid, "Second mermaid block should contain 'sequenceDiagram'")
        self.assertIn("Alice->>Bob", second_mermaid, "Second mermaid block should contain 'Alice->>Bob'")

    def test_mermaid_conversion_to_mdx(self):
        """Test that mermaid code blocks are converted to MermaidChart components in MDX"""

        # Test markdown content with mermaid
        test_md = """# Test Document

Here is a mermaid diagram:

```mermaid
graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[End]
    D --> E
```

And some regular code:

```python
print('Hello World')
```
"""

        # Create page info for conversion
        page_info = {
            "package_name": "test",
            "version": "main",
            "language": "en",
            "path": None,  # Not needed for this test
            "repo_name": "test-repo",
            "repo_owner": "test-owner",
        }

        # Convert to MDX
        result = convert_md_to_mdx(test_md, page_info)

        # Check that MermaidChart component is imported
        self.assertIn(
            'import MermaidChart from "$lib/MermaidChart.svelte";', result, "MDX should import MermaidChart component"
        )

        # Check that MermaidChart component is used
        self.assertIn("<MermaidChart", result, "MDX should contain MermaidChart component")

        # Check that regular CodeBlock component is still used
        self.assertIn("<CodeBlock", result, "MDX should still contain CodeBlock component for non-mermaid code")

        # Check that the mermaid code is base64 encoded in the component
        self.assertIn("code={`", result, "MDX should contain base64 encoded code in MermaidChart component")

    def test_mixed_code_blocks(self):
        """Test that mixed code blocks (mermaid and regular) are handled correctly"""

        test_content = """# Mixed Code Blocks Test

```mermaid
pie title Test Chart
    "A" : 40
    "B" : 60
```

```python
def hello():
    return "world"
```

```mermaid
graph LR
    A --> B
    B --> C
```

```javascript
console.log("test");
```
"""

        # Check mermaid blocks
        mermaid_blocks = re.findall(r"```mermaid\n(.*?)\n```", test_content, re.DOTALL)
        self.assertEqual(len(mermaid_blocks), 2, "Should find exactly 2 mermaid blocks")

        # Check python blocks
        python_blocks = re.findall(r"```python\n(.*?)\n```", test_content, re.DOTALL)
        self.assertEqual(len(python_blocks), 1, "Should find exactly 1 python block")

        # Check javascript blocks
        js_blocks = re.findall(r"```javascript\n(.*?)\n```", test_content, re.DOTALL)
        self.assertEqual(len(js_blocks), 1, "Should find exactly 1 javascript block")
