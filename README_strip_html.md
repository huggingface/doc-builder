# HTML Stripper for Markdown Documentation

This script strips HTML tags from markdown files and converts docstrings to clean markdown format.

## Features

- Removes all HTML tags while preserving content
- Converts docstring blocks to clean markdown with level 4 headers (`####`)
- Extracts and formats:
  - Class/function names as headers (removes `class` and `def` prefixes)
  - Anchors in double square brackets format: `[[anchor]]`
  - Source links
  - Parameter descriptions (removes bullets and bold, uses `:` separator, adds blank lines between params)
  - Return types and descriptions
- Preserves markdown code blocks and structure
- Can process single files or entire directories

## Usage

### Single File

```bash
python3 src/scripts/strip_html_from_md.py input.md -o output.md
```

Or overwrite the input file:

```bash
python3 src/scripts/strip_html_from_md.py input.md
```

### Directory Processing

Process all markdown files in a directory:

```bash
python3 src/scripts/strip_html_from_md.py docs/ -o clean_docs/
```

Process recursively:

```bash
python3 src/scripts/strip_html_from_md.py docs/ -o clean_docs/ --recursive
```

## Examples

### Before (with HTML)

```markdown
<div class="docstring border-l-2 border-t-2 pl-4 pt-3.5">

<docstring><name>class transformers.BertConfig</name><anchor>transformers.BertConfig</anchor><source>https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/models/bert/configuration_bert.py#L29</source><paramsdesc>- **vocab_size** (`int`, *optional*, defaults to 30522) --
  Vocabulary size of the BERT model.</paramsdesc></docstring>

This is the configuration class to store the configuration of a BertModel.

</div>
```

### After (clean markdown)

```markdown
#### transformers.BertConfig[[transformers.BertConfig]]

[Source](https://github.com/huggingface/transformers/blob/v4.57.1/src/transformers/models/bert/configuration_bert.py#L29)

This is the configuration class to store the configuration of a BertModel.

**Parameters:**

vocab_size (`int`, *optional*, defaults to 30522) : Vocabulary size of the BERT model.

hidden_size (`int`, *optional*, defaults to 768) : Dimensionality of the encoder layers and the pooler layer.
```

## Command-line Options

- `input` - Input markdown file or directory (required)
- `-o, --output` - Output file or directory (optional, defaults to overwriting input)
- `-r, --recursive` - Process directory recursively (optional)

## What Gets Stripped

The script removes:
- `<div>` tags and their attributes
- `<docstring>` and nested tags (`<name>`, `<anchor>`, `<source>`, etc.)
- Component tags: `<Tip>`, `<ExampleCodeBlock>`, `<hfoptions>`, `<hfoption>`, etc.
- `<EditOnGithub>` links
- HTML comments
- Any other HTML tags

## What Gets Preserved

- Markdown syntax (headers, lists, code blocks, links, etc.)
- Text content from within HTML tags
- Code blocks (backtick-fenced)
- Link URLs and formatting

