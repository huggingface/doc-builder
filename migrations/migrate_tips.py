#!/usr/bin/env python3
import argparse
import re
from pathlib import Path

TIP_PATTERN = re.compile(
    r"<Tip(?P<warning>\s+warning(?:={true})?)?>\s*(?P<body>.*?)\s*</Tip>",
    re.DOTALL,
)

def tip_to_admonition(match: re.Match) -> str:
    body = match.group("body").strip("\n")
    label = "[!WARNING]" if match.group("warning") else "[!TIP]"
    quoted_lines = "\n".join(f"> {line}" if line.strip() else ">" for line in body.splitlines())
    if not quoted_lines:
        quoted_lines = ">"
    return f"> {label}\n{quoted_lines}"

def convert_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    new_text, replaced = TIP_PATTERN.subn(tip_to_admonition, text)
    if replaced:
        path.write_text(new_text, encoding="utf-8")
    return bool(replaced)

def main() -> None:
    parser = argparse.ArgumentParser(description="Convert <Tip> blocks to [!TIP]/[!WARNING] blockquotes.")
    parser.add_argument("root", type=Path, help="File or directory containing markdown files.")
    parser.add_argument("--glob", default="**/*.md", help="Glob to select files (default: **/*.md).")
    args = parser.parse_args()

    targets = [args.root] if args.root.is_file() else sorted(args.root.glob(args.glob))
    changed = sum(convert_file(path) for path in targets if path.is_file())

    print(f"Updated {changed} file(s).")

if __name__ == "__main__":
    main()