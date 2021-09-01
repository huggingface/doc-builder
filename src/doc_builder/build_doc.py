import importlib
import os
import re
import shutil
from pathlib import Path

from tqdm import tqdm

from .autodoc import autodoc, find_object_in_package, get_shortest_path
from .convert_rst_to_mdx import convert_rst_to_mdx, find_indent, is_empty_line


_re_autodoc = re.compile("^\s*\[\[autodoc\]\]\s+(\S+)\s*$")
_re_list_item = re.compile("^\s*-\s+(\S+)\s*$")


def resolve_autodoc(content, package, return_anchors=False):
    """
    Replaces [[autodoc]] special syntax by the corresponding generated documentation in some content.
    
    Args:
    - **content** (`str`) -- The documentation to treat.
    - **package** (`types.ModuleType`) -- The package where to look for objects to document.
    - **return_anchors** (`bool`, *optional*, defaults to `False`) -- Whether or not to return the list of anchors
      generated.
    """
    lines = content.split("\n")
    new_lines = []
    if return_anchors:
        anchors = []
    idx = 0
    while idx < len(lines):
        if _re_autodoc.search(lines[idx]) is not None:
            object_name = _re_autodoc.search(lines[idx]).groups()[0]
            autodoc_indent = find_indent(lines[idx])
            idx += 1
            while idx < len(lines) and is_empty_line(lines[idx]):
                idx += 1
            if idx < len(lines) and find_indent(lines[idx]) > autodoc_indent and _re_list_item.search(lines[idx]) is not None:
                methods = []
                methods_indent = find_indent(lines[idx])
                while is_empty_line(lines[idx]) or (find_indent(lines[idx]) == methods_indent and _re_list_item.search(lines[idx]) is not None):
                    if not is_empty_line(lines[idx]):
                        methods.append(_re_list_item.search(lines[idx]).groups()[0])
                    idx += 1
                    if idx >= len(lines):
                        break
            else:
                methods = None
            doc = autodoc(object_name, package, methods=methods, return_anchors=return_anchors)
            if return_anchors:
                anchors.extend(doc[1])
                doc = doc[0]
            new_lines.append(doc)
        else:
            new_lines.append(lines[idx])
            idx += 1

    new_content = "\n".join(new_lines)
    return (new_content, anchors) if return_anchors else new_content


def build_mdx_files(package, doc_folder, output_dir):
    """
    Build the MDX files for a given package.
    
    Args:
    - **package** (`types.ModuleType`) -- The package where to look for objects to document.
    - **doc_folder** (`str` or `os.PathLike`) -- The folder where the doc source files are.
    - **output_dir** (`str` or `os.PathLike`) -- The folder where to put the files built.
    """
    doc_folder = Path(doc_folder)
    output_dir = Path(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    anchor_mapping = {} 
    
    all_files = list(doc_folder.glob("**/*"))
    for file in tqdm(all_files, desc="Building the MDX files"):
        new_anchors = None
        if file.suffix in [".md", ".mdx"]:
            dest_file = output_dir / (file.with_suffix(".mdx").relative_to(doc_folder))
            os.makedirs(dest_file.parent, exist_ok=True)
            with open(file, "r", encoding="utf-8") as reader:
                content = reader.read()
            content, new_anchors = resolve_autodoc(content, package, return_anchors=True)
            with open(dest_file, "w", encoding="utf-8") as writer:
                writer.write(content)
        elif file.suffix in [".rst"]:
            dest_file = output_dir / (file.with_suffix(".mdx").relative_to(doc_folder))
            os.makedirs(dest_file.parent, exist_ok=True)
            with open(file, "r", encoding="utf-8") as reader:
                content = reader.read()
            content = convert_rst_to_mdx(content)
            content, new_anchors = resolve_autodoc(content, package, return_anchors=True)
            with open(dest_file, "w", encoding="utf-8") as writer:
                writer.write(content)
        elif file.is_file():
            dest_file = output_dir / (file.relative_to(doc_folder))
            os.makedirs(dest_file.parent, exist_ok=True)
            shutil.copy(file, dest_file)
            
        if new_anchors is not None:
            page_name = str(file.with_suffix(".html").relative_to(doc_folder))
            anchor_mapping.update({anchor: page_name for anchor in new_anchors})
    
    return anchor_mapping


def resolve_links_in_text(text, package, mapping):
    """
    Resolve links of the form [`SomeClass`] to the link in the documentation to `SomeClass`.
    
    Args:
    - **text** (`str`) -- The text in which to convert the links.
    - **package** (`types.ModuleType`) -- The package in which to search objects for.
    - **mapping** (`Dict[str, str]`) -- The map from anchor names of objects to their page in the documentation.
    """
    def _resolve_link(search):
        object_name = search.groups()[0]
        # If the name begins with `~`, we shortcut to the last part.
        if object_name.startswith("~"):
            obj = find_object_in_package(object_name[1:], package)
            object_name = object_name.split(".")[-1]
        else:
            obj = find_object_in_package(object_name, package)
        if obj is None:
            return f"`{object_name}`"
        
        # If the object is not a class, we add ()
        if not isinstance(obj, type):
            object_name = f"{object_name}()"
        
        # Link to the anchor
        anchor = get_shortest_path(obj, package)
        if anchor not in mapping:
            return f"`{object_name}`"
        page = mapping[anchor]
        return f"[{object_name}]({page}#{anchor})"

    return re.sub(r"\[`([^`]+)`\]", _resolve_link, text)


def resolve_links(doc_folder, package, mapping):
    """
    Resolve links of the form [`SomeClass`] to the link in the documentation to `SomeClass` for all files in a
    folder.
    
    Args:
    - **doc_folder** (`str` or `os.PathLike`) -- The folder in which to look for files.
    - **package** (`types.ModuleType`) -- The package in which to search objects for.
    - **mapping** (`Dict[str, str]`) -- The map from anchor names of objects to their page in the documentation.
    """
    doc_folder = Path(doc_folder)
    all_files = list(doc_folder.glob("**/*.mdx"))
    for file in tqdm(all_files, desc="Resolving internal links"):
        with open(file, "r", encoding="utf-8") as reader:
            content = reader.read()
        content = resolve_links_in_text(content, package, mapping)
        with open(file, "w", encoding="utf-8") as writer:
            writer.write(content)


def build_doc(package_name, doc_folder, output_dir, clean=True):
    """
    Build the documentation of a package.
    
    Args:
    - **package_name** (`str`) -- The name of the package.
    - **doc_folder** (`str` or `os.PathLike) -- The folder in which the source documentation of the package is.
    - **output_dir** (`str` or `os.PathLike) -- The folder in which to put the built documentation. Will
      be created if it does not exist.
    - **clean** (`bool`, *optional*, defaults to `True`) -- Whether or not to delete the content of the
      `output_dir` if that directory exists.
    """
    if clean and Path(output_dir).exists():
        shutil.rmtree(output_dir)
    package = importlib.import_module(package_name)
    anchors_mapping = build_mdx_files(package, doc_folder, output_dir)
    resolve_links(output_dir, package, anchors_mapping)
