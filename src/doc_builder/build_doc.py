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


import importlib
import os
import re
import shutil
import zlib
from pathlib import Path

import yaml
from tqdm import tqdm

from .autodoc import autodoc, find_object_in_package, remove_example_tags, resolve_links_in_text
from .convert_md_to_mdx import convert_md_to_mdx
from .convert_rst_to_mdx import convert_rst_to_mdx, find_indent, is_empty_line
from .convert_to_notebook import generate_notebooks_from_file
from .frontmatter_node import FrontmatterNode
from .utils import read_doc_config


_re_autodoc = re.compile("^\s*\[\[autodoc\]\]\s+(\S+)\s*$")
_re_list_item = re.compile("^\s*-\s+(\S+)\s*$")


def resolve_open_in_colab(content, page_info):
    """
    Replaces [[open-in-colab]] special markers by the proper svelte component.

    Args:
        content (`str`): The documentation to treat.
        page_info (`Dict[str, str]`, *optional*): Some information about the page.
    """
    if "[[open-in-colab]]" not in content:
        return content

    package_name = page_info["package_name"]
    page_name = Path(page_info["page"]).stem
    nb_prefix = f"/github/huggingface/notebooks/blob/master/{package_name}_doc/"
    nb_prefix_colab = f"https://colab.research.google.com{nb_prefix}"
    nb_prefix_awsstudio = f"https://studiolab.sagemaker.aws/import{nb_prefix}"
    links = [
        ("Mixed", f"{nb_prefix_colab}{page_name}.ipynb"),
        ("PyTorch", f"{nb_prefix_colab}pytorch/{page_name}.ipynb"),
        ("TensorFlow", f"{nb_prefix_colab}tensorflow/{page_name}.ipynb"),
        ("Mixed", f"{nb_prefix_awsstudio}{page_name}.ipynb"),
        ("PyTorch", f"{nb_prefix_awsstudio}pytorch/{page_name}.ipynb"),
        ("TensorFlow", f"{nb_prefix_awsstudio}tensorflow/{page_name}.ipynb"),
    ]
    formatted_links = ['    {label: "' + key + '", value: "' + value + '"},' for key, value in links]

    svelte_component = """<DocNotebookDropdown
  classNames="absolute z-10 right-0 top-0"
  options={[
"""
    svelte_component += "\n".join(formatted_links)
    svelte_component += "\n]} />"

    return content.replace("[[open-in-colab]]", svelte_component)


def resolve_autodoc(content, package, return_anchors=False, page_info=None):
    """
    Replaces [[autodoc]] special syntax by the corresponding generated documentation in some content.

    Args:
        content (`str`): The documentation to treat.
        package (`types.ModuleType`): The package where to look for objects to document.
        return_anchors (`bool`, *optional*, defaults to `False`):
            Whether or not to return the list of anchors generated.
        page_info (`Dict[str, str]`, *optional*): Some information about the page.
    """
    idx_last_heading = None
    is_inside_codeblock = False
    lines = content.split("\n")
    new_lines = []
    if return_anchors:
        anchors = []
        errors = []
    idx = 0
    while idx < len(lines):
        if _re_autodoc.search(lines[idx]) is not None:
            object_name = _re_autodoc.search(lines[idx]).groups()[0]
            autodoc_indent = find_indent(lines[idx])
            idx += 1
            while idx < len(lines) and is_empty_line(lines[idx]):
                idx += 1
            if (
                idx < len(lines)
                and find_indent(lines[idx]) > autodoc_indent
                and _re_list_item.search(lines[idx]) is not None
            ):
                methods = []
                methods_indent = find_indent(lines[idx])
                while is_empty_line(lines[idx]) or (
                    find_indent(lines[idx]) == methods_indent and _re_list_item.search(lines[idx]) is not None
                ):
                    if not is_empty_line(lines[idx]):
                        methods.append(_re_list_item.search(lines[idx]).groups()[0])
                    idx += 1
                    if idx >= len(lines):
                        break
            else:
                methods = None
            doc = autodoc(object_name, package, methods=methods, return_anchors=return_anchors, page_info=page_info)
            if return_anchors:
                if len(doc[1]) and idx_last_heading is not None:
                    object_anchor = doc[1][0]
                    new_lines[idx_last_heading] += f"[[{object_anchor}]]"
                    idx_last_heading = None
                anchors.extend(doc[1])
                errors.extend(doc[2])
                doc = doc[0]
            new_lines.append(doc)
        else:
            new_lines.append(lines[idx])
            if lines[idx].startswith("```"):
                is_inside_codeblock = not is_inside_codeblock
            if lines[idx].startswith("#") and not is_inside_codeblock:
                idx_last_heading = len(new_lines) - 1
            idx += 1

    new_content = "\n".join(new_lines)
    new_content = remove_example_tags(new_content)

    return (new_content, anchors, errors) if return_anchors else new_content


def build_mdx_files(package, doc_folder, output_dir, page_info):
    """
    Build the MDX files for a given package.

    Args:
        package (`types.ModuleType`): The package where to look for objects to document.
        doc_folder (`str` or `os.PathLike`): The folder where the doc source files are.
        output_dir (`str` or `os.PathLike`): The folder where to put the files built.
        page_info (`Dict[str, str]`): Some information about the page.
    """
    doc_folder = Path(doc_folder)
    output_dir = Path(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    anchor_mapping = {}

    if "package_name" not in page_info:
        page_info["package_name"] = package.__name__

    all_files = list(doc_folder.glob("**/*"))
    all_errors = []
    for file in tqdm(all_files, desc="Building the MDX files"):
        new_anchors = None
        errors = None
        try:
            if file.suffix in [".md", ".mdx"]:
                dest_file = output_dir / (file.with_suffix(".mdx").relative_to(doc_folder))
                page_info["page"] = file.with_suffix(".html").relative_to(doc_folder)
                os.makedirs(dest_file.parent, exist_ok=True)
                with open(file, "r", encoding="utf-8-sig") as reader:
                    content = reader.read()
                content = convert_md_to_mdx(content, page_info)
                content = resolve_open_in_colab(content, page_info)
                content, new_anchors, errors = resolve_autodoc(
                    content, package, return_anchors=True, page_info=page_info
                )
                with open(dest_file, "w", encoding="utf-8") as writer:
                    writer.write(content)
                # Make sure we clean up for next page.
                del page_info["page"]
            elif file.suffix in [".rst"]:
                dest_file = output_dir / (file.with_suffix(".mdx").relative_to(doc_folder))
                page_info["page"] = file.with_suffix(".html").relative_to(doc_folder)
                os.makedirs(dest_file.parent, exist_ok=True)
                with open(file, "r", encoding="utf-8") as reader:
                    content = reader.read()
                content = convert_rst_to_mdx(content, page_info)
                content = resolve_open_in_colab(content, page_info)
                content, new_anchors, errors = resolve_autodoc(
                    content, package, return_anchors=True, page_info=page_info
                )
                with open(dest_file, "w", encoding="utf-8") as writer:
                    writer.write(content)
                # Make sure we clean up for next page.
                del page_info["page"]
            elif file.is_file():
                dest_file = output_dir / (file.relative_to(doc_folder))
                os.makedirs(dest_file.parent, exist_ok=True)
                shutil.copy(file, dest_file)

        except Exception as e:
            raise type(e)(f"There was an error when converting {file} to the MDX format.\n" + e.args[0]) from e

        if new_anchors is not None:
            page_name = str(file.with_suffix("").relative_to(doc_folder))
            anchor_mapping.update({anchor: page_name for anchor in new_anchors})

        if errors is not None:
            all_errors.extend(errors)

    if len(all_errors) > 0:
        raise ValueError(
            "The deployment of the documentation will fail because of the following errors:\n" + "\n".join(all_errors)
        )

    return anchor_mapping


def resolve_links(doc_folder, package, mapping, page_info):
    """
    Resolve links of the form [`SomeClass`] to the link in the documentation to `SomeClass` for all files in a
    folder.

    Args:
        doc_folder (`str` or `os.PathLike`): The folder in which to look for files.
        package (`types.ModuleType`): The package in which to search objects for.
        mapping (`Dict[str, str]`): The map from anchor names of objects to their page in the documentation.
        page_info (`Dict[str, str]`): Some information about the page.
    """
    doc_folder = Path(doc_folder)
    all_files = list(doc_folder.glob("**/*.mdx"))
    for file in tqdm(all_files, desc="Resolving internal links"):
        with open(file, "r", encoding="utf-8") as reader:
            content = reader.read()
        content = resolve_links_in_text(content, package, mapping, page_info)
        with open(file, "w", encoding="utf-8") as writer:
            writer.write(content)


def generate_frontmatter_in_text(text, file_name=None):
    """
    Adds frontmatter & turns markdown headers into markdown headers with hash links.

    Args:
        text (`str`): The text in which to convert the links.
    """
    text = text.split("\n")
    root = None
    is_inside_codeblock = False
    for idx, line in enumerate(text):
        if line.startswith("```"):
            is_inside_codeblock = not is_inside_codeblock
        if is_inside_codeblock or is_empty_line(line):
            continue
        header_search = re.search(r"^(#+)\s+(\S.*)$", line)
        if header_search is None:
            continue
        first_word, title = header_search.groups()
        header_level = len(first_word)
        serach_local = re.search(r"\[\[(.*)]]", title)
        if serach_local:
            # id/local already exists
            local = serach_local.group(1)
            title = re.sub(r"\[\[(.*)]]", "", title)
        else:
            # create id/local
            local = re.sub(r"[^a-z0-9\s]+", "", title.lower())
            local = re.sub(r"\s{2,}", " ", local.strip()).replace(" ", "-")
        text[idx] = f'<h{header_level} id="{local}">{title}</h{header_level}>'
        node = FrontmatterNode(title, local)
        if header_level == 1:
            root = node
        else:
            if root is None:
                raise ValueError(
                    f"{file_name} does not contain a level 1 header (more commonly known as title) before the first "
                    " second (or more) level header. Make sure to include one!"
                )
            root.add_child(node, header_level)

    frontmatter = root.get_frontmatter()
    text = "\n".join(text)
    text = frontmatter + text
    return text


def generate_frontmatter(doc_folder):
    """
    Adds frontmatter & turns markdown headers into markdown headers with hash links for all files in a folder.

    Args:
        doc_folder (`str` or `os.PathLike`): The folder in which to look for files.
    """
    doc_folder = Path(doc_folder)
    all_files = list(doc_folder.glob("**/*.mdx"))
    for file_name in tqdm(all_files, desc="Generating frontmatter"):
        # utf-8-sig is needed to correctly open community.md file
        with open(file_name, "r", encoding="utf-8-sig") as reader:
            content = reader.read()
        content = generate_frontmatter_in_text(content, file_name=file_name)
        with open(file_name, "w", encoding="utf-8") as writer:
            writer.write(content)


def build_notebooks(doc_folder, notebook_dir, package=None, mapping=None, page_info=None):
    """
    Build the notebooks associated to the MDX files in the documentation with an [[open-in-colab]] marker.

    Args:
        doc_folder (`str` or `os.PathLike`): The folder where the doc source files are.
        notebook_dir_dir (`str` or `os.PathLike`): Where to save the generated notebooks
        package (`types.ModuleType`, *optional*):
            The package in which to search objects for (needs to be passed to resolve doc links).
        mapping (`Dict[str, str]`, *optional*):
            The map from anchor names of objects to their page in the documentation (needs to be passed to resolve doc
            links).
        page_info (`Dict[str, str]`, *optional*):
            Some information about the page (needs to be passed to resolve doc links).
    """
    doc_folder = Path(doc_folder)

    if "package_name" not in page_info:
        page_info["package_name"] = package.__name__

    mdx_files = list(doc_folder.glob("**/*.mdx"))
    for file in tqdm(mdx_files, desc="Building the notebooks"):
        with open(file, "r", encoding="utf-8") as f:
            if "[[open-in-colab]]" not in f.read():
                continue
        try:
            page_info["page"] = file.with_suffix(".html").relative_to(doc_folder)
            generate_notebooks_from_file(file, notebook_dir, package=package, mapping=mapping, page_info=page_info)
            # Make sure we clean up for next page.
            del page_info["page"]

        except Exception as e:
            raise type(e)(f"There was an error when converting {file} to a notebook.\n" + e.args[0]) from e


def build_doc(package_name, doc_folder, output_dir, clean=True, version="master", language="en", notebook_dir=None):
    """
    Build the documentation of a package.

    Args:
        package_name (`str`): The name of the package.
        doc_folder (`str` or `os.PathLike`): The folder in which the source documentation of the package is.
        output_dir (`str` or `os.PathLike`):
            The folder in which to put the built documentation. Will be created if it does not exist.
        clean (`bool`, *optional*, defaults to `True`):
            Whether or not to delete the content of the `output_dir` if that directory exists.
        version (`str`, *optional*, defaults to `"master"`): The name of the version of the doc.
        language (`str`, *optional*, defaults to `"en"`): The language of the doc.
        notebook_dir (`str` or `os.PathLike`, *optional*):
            If provided, where to save the notebooks generated from the doc file with an [[open-in-colab]] marker.
    """
    page_info = {"version": version, "language": language, "package_name": package_name}
    if clean and Path(output_dir).exists():
        shutil.rmtree(output_dir)

    read_doc_config(doc_folder)

    package = importlib.import_module(package_name)
    anchors_mapping = build_mdx_files(package, doc_folder, output_dir, page_info)
    sphinx_refs = check_toc_integrity(doc_folder, output_dir)
    sphinx_refs.extend(convert_anchors_mapping_to_sphinx_format(anchors_mapping, package))
    build_sphinx_objects_ref(sphinx_refs, output_dir, page_info)
    resolve_links(output_dir, package, anchors_mapping, page_info)
    generate_frontmatter(output_dir)

    if notebook_dir is not None:
        if clean and Path(notebook_dir).exists():
            for nb_file in Path(notebook_dir).glob("**/*.ipynb"):
                os.remove(nb_file)
        build_notebooks(doc_folder, notebook_dir, package=package, mapping=anchors_mapping, page_info=page_info)


def check_toc_integrity(doc_folder, output_dir):
    """
    Checks all the MDX files obtained after building the documentation are present in the table of contents.

    Args:
        doc_folder (`str` or `os.PathLike`): The folder where the source files of the documentation lie.
        output_dir (`str` or `os.PathLike`): The folder where the doc is built.
    """
    output_dir = Path(output_dir)
    doc_files = [str(f.relative_to(output_dir).with_suffix("")) for f in output_dir.glob("**/*.mdx")]

    toc_file = Path(doc_folder) / "_toctree.yml"
    with open(toc_file, "r", encoding="utf-8") as f:
        toc = yaml.safe_load(f.read())

    toc_sections = []
    sphinx_refs = []
    # We don't just loop directly in toc as we will add more into it as we un-nest things.
    while len(toc) > 0:
        part = toc.pop(0)
        toc_sections.extend([sec["local"] for sec in part["sections"] if "local" in sec])
        # There should be one sphinx ref per page
        for sec in part["sections"]:
            if "local" in sec:
                sphinx_refs.append(f"{sec['local']} std:doc -1 {sec['local']} {sec['title']}")
        # Toc has some nested sections in the API doc for instance, so we recurse.
        toc.extend([sec for sec in part["sections"] if "sections" in sec])

    files_not_in_toc = [f for f in doc_files if f not in toc_sections]
    if len(files_not_in_toc) > 0:
        message = "\n".join([f"- {f}" for f in files_not_in_toc])
        raise RuntimeError(
            "The following files are not present in the table of contents:\n" + message + f"\nAdd them to {toc_file}."
        )

    files_not_exist = [f for f in toc_sections if f not in doc_files]
    if len(files_not_exist) > 0:
        message = "\n".join([f"- {f}" for f in files_not_exist])
        raise RuntimeError(
            "The following files are present in the table of contents but do not exist:\n"
            + message
            + f"\nRemove them from {toc_file}."
        )

    return sphinx_refs


def convert_anchors_mapping_to_sphinx_format(anchors_mapping, package):
    """
    Convert the anchor mapping to the format expected by sphinx for the `objects.inv` file.

    Args:
        anchors_mapping (Dict[`str`, `str`]):
            The mapping between anchors for objects in the doc and their location in the doc.
        package (`types.ModuleType`):
            The package in which to search objects for.
    """
    sphinx_refs = []
    for anchor, url in anchors_mapping.items():
        obj = find_object_in_package(anchor, package)
        if isinstance(obj, property):
            obj = obj.fget

        # Object type
        if isinstance(obj, type):
            obj_type = "py:class"
        elif hasattr(obj, "__name__") and hasattr(obj, "__qualname__"):
            obj_type = "py:method" if obj.__name__ != obj.__qualname__ else "py:function"
        else:
            # Default to function (this part is never hit when building the docs for Transformers and Datasets)
            # so it's just to be extra defensive
            obj_type = "py:function"

        sphinx_refs.append(f"{anchor} {obj_type} 1 {url}#$ -")

    return sphinx_refs


def build_sphinx_objects_ref(sphinx_refs, output_dir, page_info):
    """
    Saves the sphinx references in an `objects.inv` file that can then be used by other documentations powered by
    sphinx to link to objects in the generated doc.

    Args:
        sphinx_refs (`List[str]`): The list of all references, in the format expected by sphinx.
        output_dir (`str` or `os.PathLike`): The folder where the doc is built.
        page_info (`Dict[str, str]`): Some information about the doc.
    """
    intro = [
        "# Sphinx inventory version 2\n",
        f"# Project: {page_info['package_name']}\n",
        f"# Version: {page_info['version']}\n",
        "# The remainder of this file is compressed using zlib.\n",
    ]
    lines = [str.encode(line) for line in intro]

    data = "\n".join(sorted(sphinx_refs)) + "\n"
    data = zlib.compress(str.encode(data))

    with open(Path(output_dir) / "objects.inv", "wb") as f:
        f.writelines(lines)
        f.write(data)
