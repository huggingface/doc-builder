#!/usr/bin/env python3
"""
Script to strip HTML from markdown files and convert docstrings to clean markdown.

Specifically handles docstring blocks by:
- Removing all HTML tags
- Converting class/function names to level 4 headers (####)
- Preserving the text content
"""

import re
import argparse
from pathlib import Path
from html.parser import HTMLParser
from typing import Optional


class HTMLStripper(HTMLParser):
    """Helper class to strip HTML tags while preserving text content."""
    
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
    
    def handle_data(self, data):
        self.text.append(data)
    
    def get_data(self):
        return ''.join(self.text)


def strip_html_tags(text: str) -> str:
    """Strip HTML tags from text while preserving content."""
    stripper = HTMLStripper()
    stripper.feed(text)
    return stripper.get_data()


def extract_docstring_info(docstring_block: str) -> dict:
    """Extract information from a docstring block."""
    info = {
        'name': None,
        'anchor': None,
        'source': None,
        'parameters': None,
        'paramsdesc': None,
        'rettype': None,
        'retdesc': None,
        'description': None
    }
    
    # Extract name
    name_match = re.search(r'<name>(.*?)</name>', docstring_block, re.DOTALL)
    if name_match:
        raw_name = name_match.group(1).strip()
        # Remove "class " or "def " prefix if present
        cleaned_name = re.sub(r'^(class|def)\s+', '', raw_name)
        info['name'] = cleaned_name
    
    # Extract anchor
    anchor_match = re.search(r'<anchor>(.*?)</anchor>', docstring_block, re.DOTALL)
    if anchor_match:
        info['anchor'] = anchor_match.group(1).strip()
    
    # Extract source
    source_match = re.search(r'<source>(.*?)</source>', docstring_block, re.DOTALL)
    if source_match:
        info['source'] = source_match.group(1).strip()
    
    # Extract parameters description
    paramsdesc_match = re.search(r'<paramsdesc>(.*?)</paramsdesc>', docstring_block, re.DOTALL)
    if paramsdesc_match:
        info['paramsdesc'] = paramsdesc_match.group(1).strip()
    
    # Extract return type
    rettype_match = re.search(r'<rettype>(.*?)</rettype>', docstring_block, re.DOTALL)
    if rettype_match:
        info['rettype'] = rettype_match.group(1).strip()
    
    # Extract return description
    retdesc_match = re.search(r'<retdesc>(.*?)</retdesc>', docstring_block, re.DOTALL)
    if retdesc_match:
        info['retdesc'] = retdesc_match.group(1).strip()
    
    # Extract text outside docstring tags but inside the div
    # This is the description text
    description_match = re.search(r'</docstring>(.*?)(?:</div>|$)', docstring_block, re.DOTALL)
    if description_match:
        desc_text = description_match.group(1).strip()
        # Remove any remaining HTML tags
        desc_text = re.sub(r'<[^>]+>', '', desc_text)
        if desc_text:
            info['description'] = desc_text
    
    return info


def format_parameters(paramsdesc: str) -> str:
    """
    Format parameter descriptions by:
    - Removing bullets (-)
    - Removing bold formatting (**)
    - Changing -- to :
    - Adding blank lines between parameters
    """
    lines = paramsdesc.split('\n')
    formatted_params = []
    current_param = []
    
    for line in lines:
        # Check if this is a new parameter line (starts with "- **")
        if re.match(r'^\s*-\s+\*\*', line):
            # Save the previous parameter if exists
            if current_param:
                param_text = ' '.join(current_param)
                # Remove - and ** formatting
                param_text = re.sub(r'^\s*-\s+\*\*([^*]+)\*\*', r'\1', param_text)
                # Change -- to :
                param_text = re.sub(r'\s+--\s+', ' : ', param_text, count=1)
                formatted_params.append(param_text)
                formatted_params.append('')  # Add blank line between parameters
                current_param = []
            
            # Start new parameter
            current_param.append(line)
        elif current_param:
            # Continuation of current parameter description
            current_param.append(line.strip())
    
    # Don't forget the last parameter
    if current_param:
        param_text = ' '.join(current_param)
        param_text = re.sub(r'^\s*-\s+\*\*([^*]+)\*\*', r'\1', param_text)
        param_text = re.sub(r'\s+--\s+', ' : ', param_text, count=1)
        formatted_params.append(param_text)
    
    return '\n'.join(formatted_params)


def process_docstring_block(docstring_block: str) -> str:
    """
    Process a docstring block by:
    1. Extracting the class/function name and relevant info
    2. Stripping all HTML tags
    3. Converting to clean markdown with level 4 header
    """
    # Extract structured information from the docstring
    info = extract_docstring_info(docstring_block)
    
    # Build the cleaned markdown
    parts = []
    
    # Add the name as level 4 header with anchor
    if info['name']:
        if info['anchor']:
            parts.append(f"#### {info['name']}[[{info['anchor']}]]")
        else:
            parts.append(f"#### {info['name']}")
        parts.append("")
    
    # Add source link if available
    if info['source']:
        # Strip any HTML from source
        source_clean = strip_html_tags(info['source'])
        parts.append(f"[Source]({source_clean})")
        parts.append("")
    
    # Add description
    if info['description']:
        parts.append(info['description'])
        parts.append("")
    
    # Add parameters description
    if info['paramsdesc']:
        parts.append("**Parameters:**")
        parts.append("")
        # Format parameters: remove bullets and bold, change -- to :, add blank lines
        formatted_params = format_parameters(info['paramsdesc'])
        parts.append(formatted_params)
        parts.append("")
    
    # Add return type
    if info['rettype']:
        parts.append("**Returns:**")
        parts.append("")
        # Strip HTML tags from return type
        rettype_clean = strip_html_tags(info['rettype'])
        parts.append(f"`{rettype_clean}`")
        parts.append("")
    
    # Add return description
    if info['retdesc']:
        if not info['rettype']:
            parts.append("**Returns:**")
            parts.append("")
        parts.append(info['retdesc'])
        parts.append("")
    
    result = '\n'.join(parts)
    
    # Clean up excessive newlines
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result.strip()


def strip_html_from_markdown(content: str) -> str:
    """
    Strip HTML from markdown content.
    
    Handles:
    - Docstring blocks wrapped in <div class="docstring...">...</div>
    - Other HTML tags throughout the document
    """
    result = content
    
    # Process docstring blocks with their wrapping divs
    # Pattern to match: <div class="docstring...">...<docstring>...</docstring>...</div>
    docstring_pattern = r'<div[^>]*class="docstring[^"]*"[^>]*>.*?<docstring>.*?</docstring>.*?</div>'
    
    def replace_docstring(match):
        block = match.group(0)
        return process_docstring_block(block)
    
    result = re.sub(docstring_pattern, replace_docstring, result, flags=re.DOTALL)
    
    # Strip remaining HTML tags (like <Tip>, </Tip>, <ExampleCodeBlock>, etc.)
    # But preserve markdown code blocks
    result = strip_remaining_html(result)
    
    return result


def strip_remaining_html(content: str) -> str:
    """
    Strip remaining HTML tags while preserving markdown structure.
    Handles tags like <Tip>, <ExampleCodeBlock>, etc.
    """
    # Remove HTML comments
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    
    # Remove common component tags while preserving their content
    # (Tip, TipEnd, ExampleCodeBlock, hfoptions, hfoption, etc.)
    tags_to_remove = [
        'Tip', 'TipEnd', 'ExampleCodeBlock', 'hfoptions', 'hfoption',
        'EditOnGithub', 'div', 'span', 'anchor'
    ]
    
    for tag in tags_to_remove:
        # Remove opening tags with any attributes
        content = re.sub(rf'<{tag}[^>]*>', '', content, flags=re.IGNORECASE)
        # Remove closing tags
        content = re.sub(rf'</{tag}>', '', content, flags=re.IGNORECASE)
    
    # Remove any remaining HTML tags (generic cleanup)
    # This is more aggressive but preserves text content
    content = re.sub(r'<[^>]+>', '', content)
    
    # Clean up multiple consecutive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content


def process_file(input_path: Path, output_path: Optional[Path] = None) -> None:
    """
    Process a markdown file to strip HTML.
    
    Args:
        input_path: Path to input markdown file
        output_path: Path to output file (if None, overwrites input)
    """
    # Read the input file
    content = input_path.read_text(encoding='utf-8')
    
    # Process the content
    cleaned_content = strip_html_from_markdown(content)
    
    # Write to output file
    if output_path is None:
        output_path = input_path
    
    output_path.write_text(cleaned_content, encoding='utf-8')
    print(f"Processed: {input_path} -> {output_path}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Strip HTML from markdown files and convert docstrings to clean markdown.'
    )
    parser.add_argument(
        'input',
        type=str,
        help='Input markdown file or directory'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Output file or directory (defaults to overwriting input)'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Process directory recursively'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None
    
    if input_path.is_file():
        # Process single file
        process_file(input_path, output_path)
    elif input_path.is_dir():
        # Process directory
        pattern = '**/*.md' if args.recursive else '*.md'
        md_files = list(input_path.glob(pattern))
        
        if not md_files:
            print(f"No markdown files found in {input_path}")
            return
        
        for md_file in md_files:
            if output_path:
                # Preserve directory structure in output
                relative_path = md_file.relative_to(input_path)
                out_file = output_path / relative_path
                out_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_file = None
            
            process_file(md_file, out_file)
        
        print(f"\nProcessed {len(md_files)} file(s)")
    else:
        print(f"Error: {input_path} is not a valid file or directory")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())

