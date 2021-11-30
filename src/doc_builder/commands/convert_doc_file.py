import argparse
import re
from pathlib import Path

from doc_builder.convert_rst_to_mdx import convert_rst_to_mdx


def find_root_git(folder):
    "Finds the first parent folder who is a git directory or returns None if there is no git directory."
    folder = Path(folder).absolute()
    while folder != folder.parent and not (folder / ".git").exists():
        folder = folder.parent
    return folder if folder != folder.parent else None


def convert_command(args):
    source_file = Path(args.source_file).absolute()
    if args.package_name is None:
        git_folder = find_root_git(source_file)
        if git_folder is None:
            raise ValueError(
                "Cannot determine a default for package_name as the file passed is not in a git directory. "
                "Please pass along a package_name."
            )
        package_name = git_folder.name
    else:
        package_name = args.package_name
    
    if args.output_file is None:
        output_file = source_file.with_suffix(".mdx")
    else:
        output_file = args.output_file
    
    if args.doc_folder is None:
        git_folder = find_root_git(source_file)
        if git_folder is None:
            raise ValueError(
                "Cannot determine a default for package_name as the file passed is not in a git directory. "
                "Please pass along a package_name."
            )
        doc_folder = git_folder / "docs/source"
        if doc_folder / source_file.relative_to(doc_folder) != source_file:
            raise ValueError(
                f"The default found for `doc_folder` is {doc_folder} but it does not look like {source_file} is "
                "inside it."
            )
    else:
        doc_folder = args.doc_folder
        
    with open(source_file, "r", encoding="utf-8") as f:
        text = f.read()
    
    page_info = {"package_name": package_name, "page": source_file.with_suffix(".html").relative_to(doc_folder)}
    text = convert_rst_to_mdx(text, page_info, add_imports=False)
    text = re.sub(r"^\[\[autodoc\]\](\s+)(transformers\.)", r"[[autodoc]]\1", text, flags=re.MULTILINE)
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(text)


def convert_command_parser(subparsers=None):
    if subparsers is not None:
        parser = subparsers.add_parser("convert")
    else:
        parser = argparse.ArgumentParser("Doc Builder convert command")

    parser.add_argument("source_file", type=str, help="The file to convert.")
    parser.add_argument(
        "--package_name",
        type=str,
        default=None,
        help="The name of the package this doc file belongs to. Will default to the name of the root git repo "
             "`source_file` is in."
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default=None,
        help="Where to save the converted file. Will default to the `source_file` with an mdx suffix."
    )
    parser.add_argument(
        "--doc_folder",
        type=str,
        help="Version under which to push the files. Will not affect the actual files generated, as these are"
             " generated according to the `path_to_docs` argument.",
    )

    if subparsers is not None:
        parser.set_defaults(func=convert_command)
    return parser
