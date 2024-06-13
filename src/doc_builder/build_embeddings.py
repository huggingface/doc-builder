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
import time
from collections import namedtuple
from pathlib import Path
from typing import List

import requests
from tqdm import tqdm

from .autodoc import autodoc_markdown, resolve_links_in_text
from .convert_md_to_mdx import process_md
from .convert_rst_to_mdx import find_indent, is_empty_line
from .utils import read_doc_config


Chunk = namedtuple("Chunk", "text source package_name")
Embedding = namedtuple("Chunk", "text source package_name embedding")


class MarkdownChunkNode:
    def __init__(self, heading):
        self.heading, self.local = self.create_local(heading)
        self.children = []
        self.content = ""

    def create_local(self, heading):
        serach_local = re.search(r"\[\[(.*)]]", heading)
        if serach_local:
            # id/local already exists
            local = serach_local.group(1)
            heading = re.sub(r"\[\[(.*)]]", "", heading)
            return heading, local
        else:
            # create id/local
            local = re.sub(r"[^a-z0-9\s]+", "", heading.lower())
            local = re.sub(r"\s{2,}", " ", local.strip()).replace(" ", "-")
            return heading, local

    def add_child(self, child, header_level):
        parent = self
        nested_level = header_level - 2
        while nested_level:
            if not parent.children:
                parent.children.append(MarkdownChunkNode(None, None))
            parent = parent.children[-1]
            nested_level -= 1
        parent.children.append(child)

    def get_chunks(self, page_info, chunk_len_chars=50, prefix=[]):
        chunks = []
        prefix = prefix + [self.heading]
        prefix_str = "\n".join(prefix) + "\n"
        split_content = self.split_markdown(self.content)
        if not len(split_content):
            return []
        chunk = prefix_str
        for content in split_content:
            if len(chunk) > chunk_len_chars:
                # todo: add source dawg
                chunks.append(
                    Chunk(
                        text=chunk.strip(),
                        source=f"{page_info['page']}#{self.local}",
                        package_name=page_info["package_name"],
                    )
                )
                chunk = prefix_str
            chunk += content + " "
        if len(chunk) > len(prefix_str):
            chunks.append(
                Chunk(
                    text=chunk.strip(),
                    source=f"{page_info['page']}#{self.local}",
                    package_name=page_info["package_name"],
                )
            )

        for child in self.children:
            child_chunks = child.get_chunks(page_info, chunk_len_chars, prefix=prefix)
            chunks.extend(child_chunks)

        return chunks

    def split_markdown(self, text):
        # split markdown on periods & code blocks
        code_block_pattern = re.compile(r"(```.*?```)", re.DOTALL)
        segments = code_block_pattern.split(text)

        result = []

        for segment in segments:
            if segment.startswith("```") and segment.endswith("```"):
                result.append(segment)
            else:
                subsegments = re.split(r"\.\s+|\.$", segment)
                result.extend([s.strip() for s in subsegments if s.strip()])

        return result


_re_autodoc = re.compile(r"^\s*\[\[autodoc\]\]\s+(\S+)\s*$")
_re_list_item = re.compile(r"^\s*-\s+(\S+)\s*$")


def create_autodoc_chunks(content, package, return_anchors=False, page_info=None, version_tag_suffix="src/"):
    """
    Replaces [[autodoc]] special syntax by the corresponding generated documentation in some content.

    Args:
        content (`str`): The documentation to treat.
        package (`types.ModuleType`): The package where to look for objects to document.
        return_anchors (`bool`, *optional*, defaults to `False`):
            Whether or not to return the list of anchors generated.
        page_info (`Dict[str, str]`, *optional*): Some information about the page.
        version_tag_suffix (`str`, *optional*, defaults to `"src/"`):
            Suffix to add after the version tag (e.g. 1.3.0 or main) in the documentation links.
            For example, the default `"src/"` suffix will result in a base link as `https://github.com/huggingface/{package_name}/blob/{version_tag}/src/`.
            For example, `version_tag_suffix=""` will result in a base link as `https://github.com/huggingface/{package_name}/blob/{version_tag}/`.
    """
    lines = content.split("\n")
    autodoc_chunks = []
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
            object_docs, new_anchors, new_errors = autodoc_markdown(
                object_name,
                package,
                methods=methods,
                return_anchors=return_anchors,
                page_info=page_info,
                version_tag_suffix=version_tag_suffix,
            )

            object_doc_chunks = [
                Chunk(
                    text=od["doc"],
                    source=f"{page_info['page']}#{od['anchor_name']}",
                    package_name=page_info["package_name"],
                )
                for od in object_docs
            ]

            autodoc_chunks.extend(object_doc_chunks)

            if return_anchors:
                # if len(doc[1]) and idx_last_heading is not None:
                #     object_anchor = doc[1][0]
                #     autodoc_chunks[idx_last_heading] += f"[[{object_anchor}]]"
                #     idx_last_heading = None
                anchors.extend(new_anchors)
                errors.extend(new_errors)

        else:
            idx += 1

    return (autodoc_chunks, anchors, errors) if return_anchors else autodoc_chunks


def create_markdown_chunks(text, page_info=None):
    # todo: replace code blocks
    CODE_COMMENT_ESCAPE = "ESCAPE-PYTHON-CODE-COMMENT"
    _re_codeblock = re.compile(r"```.+?```", re.DOTALL)
    text = _re_codeblock.sub(lambda m: m[0].replace("#", CODE_COMMENT_ESCAPE), text)

    # Insert a newline at the start if not present to standardize the split process
    if not text.startswith("\n"):
        text = "\n" + text

    # Split by headers, keeping the headers as delimiters
    sections = re.split(r"(\n#+ [^\n]+)", text)

    # Organize the content under each heading
    root = None
    node = None

    # Loop through sections to associate text with headings
    for section in sections:
        if section.strip() and re.match(r"\n#+ [^\n]+", section):
            heading = section.strip()
            heading_level = heading.count("#")
            node = MarkdownChunkNode(heading)
            if heading_level == 1:
                root = node
            else:
                root.add_child(node, heading_level)
        elif node:
            section.replace(CODE_COMMENT_ESCAPE, "#")
            node.content += section.strip()

    if root is None:
        return []

    chunks = root.get_chunks(page_info, chunk_len_chars=400)
    return chunks


_re_html_comment = re.compile(r"<!--.+?-->", re.DOTALL)
_re_framework_pytorch = re.compile(r"<frameworkcontent>.+?<pt>(.+?)<\/pt>.+?<\/frameworkcontent>", re.DOTALL)


def clean_md(text):
    text = text.replace("[[open-in-colab]]", "")
    text = _re_html_comment.sub("", text)
    text = _re_framework_pytorch.sub(lambda m: m.group(1).strip(), text)
    return text.strip()


_re_autodoc_all = re.compile(r"(\[\[autodoc\]\]\s+[\w\.]+(?:\n\s+-\s+\w+)*\b)", re.DOTALL)


def create_chunks(package, doc_folder, page_info, version_tag_suffix, is_python_module) -> List[Chunk]:
    """
    Build the MDX files for a given package.

    Args:
        package (`types.ModuleType`): The package where to look for objects to document.
        doc_folder (`str` or `os.PathLike`): The folder where the doc source files are.
        page_info (`Dict[str, str]`): Some information about the page.
        version_tag_suffix (`str`, *optional*, defaults to `"src/"`):
            Suffix to add after the version tag (e.g. 1.3.0 or main) in the documentation links.
            For example, the default `"src/"` suffix will result in a base link as `https://github.com/huggingface/{package_name}/blob/{version_tag}/src/`.
            For example, `version_tag_suffix=""` will result in a base link as `https://github.com/huggingface/{package_name}/blob/{version_tag}/`.
    """
    doc_folder = Path(doc_folder)
    anchor_mapping = {}

    if "package_name" not in page_info:
        page_info["package_name"] = package.__name__

    chunks = []
    all_files = list(doc_folder.glob("**/*"))
    all_errors = []
    for file in tqdm(all_files, desc="Building the chunks to embed"):
        new_anchors = None
        errors = None
        page_info["path"] = file
        try:
            if file.suffix in [".md", ".mdx"]:
                page_info["page"] = file.with_suffix("").relative_to(doc_folder).as_posix()
                with open(file, "r", encoding="utf-8-sig") as reader:
                    content = reader.read()
                content = clean_md(content)
                content = process_md(content, page_info)
                autodoc_content = "\n\n".join(_re_autodoc_all.findall(content))
                content = _re_autodoc_all.sub("", content)
                autodoc_chunks, new_anchors, errors = create_autodoc_chunks(
                    autodoc_content,
                    package,
                    return_anchors=True,
                    page_info=page_info,
                    version_tag_suffix=version_tag_suffix,
                )
                markdown_chunks = create_markdown_chunks(
                    content,
                    page_info=page_info,
                )

                # Make sure we clean up for next page.
                del page_info["page"]

                page_chunks = markdown_chunks + autodoc_chunks

                if is_python_module:
                    page_chunks = [
                        chunk._replace(text=resolve_links_in_text(chunk.text, package, anchor_mapping, page_info))
                        for chunk in page_chunks
                    ]

                chunks.extend(page_chunks)

        except Exception as e:
            raise type(e)(f"There was an error when converting {file} to chunks to embed.\n" + e.args[0]) from e

        if new_anchors is not None:
            page_name = str(file.with_suffix("").relative_to(doc_folder))
            for anchor in new_anchors:
                if isinstance(anchor, tuple):
                    anchor_mapping.update(
                        {a: f"{page_name}#{anchor[0]}" for a in anchor[1:] if a not in anchor_mapping}
                    )
                    anchor = anchor[0]
                anchor_mapping[anchor] = page_name

        if errors is not None:
            all_errors.extend(errors)

    if len(all_errors) > 0:
        raise ValueError(
            "The deployment of the documentation will fail because of the following errors:\n" + "\n".join(all_errors)
        )

    return chunks


def call_embed_api(chunks: List[Chunk]) -> List[Embedding]:
    """
    Using https://huggingface.co/inference-endpoints with a text embedding model
    """
    batch_size = 32
    chunks_len = len(chunks)
    embeddings = []

    API_URL = os.environ["HF_EMBED_URL"]
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {os.environ['HF_EMBED_API_KEY']}",
        "Content-Type": "application/json",
    }

    def query(payload):
        response = requests.post(API_URL, headers=headers, json=payload)
        return response.json()

    # warm up API call
    output_warmup = query({"inputs": "Hello World!"})
    if isinstance(output_warmup, dict) and "error" in output_warmup:
        if output_warmup["error"] == "503 Service Unavailable":
            print("Waking up Embedding Inference Endpoints. Retrying in 5 minutes")
            time.sleep(300)  # 5 minutes
        else:
            raise Exception("Embedding Inference Endpoints error", output_warmup["error"])

    for i in tqdm(range(0, chunks_len, batch_size), desc="Calling Embedding Inference Endpoints"):
        batch_chunk = chunks[i : i + batch_size]
        batch_chunk_texts = [chunk.text for chunk in batch_chunk]

        batch_embeddings = query({"inputs": batch_chunk_texts})

        for chunk, _embedding in zip(batch_chunk, batch_embeddings):
            embeddings = Embedding(
                text=chunk.text, source=chunk.source, package_name=chunk.package_name, embedding=_embedding
            )
            embeddings.append(embeddings)

    return embeddings


def build_embeddings(
    package_name,
    doc_folder,
    version="main",
    version_tag="main",
    language="en",
    is_python_module=False,
    version_tag_suffix="src/",
    repo_owner="huggingface",
    repo_name=None,
):
    """
    Build the documentation of a package.

    Args:
        package_name (`str`): The name of the package.
        doc_folder (`str` or `os.PathLike`): The folder in which the source documentation of the package is.
        version (`str`, *optional*, defaults to `"main"`): The name of the version of the doc.
        version_tag (`str`, *optional*, defaults to `"main"`): The name of the version tag (on GitHub) of the doc.
        language (`str`, *optional*, defaults to `"en"`): The language of the doc.
        is_python_module (`bool`, *optional*, defaults to `False`):
            Whether the docs being built are for python module. (For example, HF Course is not a python module).
        version_tag_suffix (`str`, *optional*, defaults to `"src/"`):
            Suffix to add after the version tag (e.g. 1.3.0 or main) in the documentation links.
            For example, the default `"src/"` suffix will result in a base link as `https://github.com/huggingface/{package_name}/blob/{version_tag}/src/`.
            For example, `version_tag_suffix=""` will result in a base link as `https://github.com/huggingface/{package_name}/blob/{version_tag}/`.
        repo_owner (`str`, *optional*, defaults to `"huggingface"`):
            The owner of the repository on GitHub. In most cases, this is `"huggingface"`. However, for the `timm` library, the owner is `"rwightman"`.
        repo_name (`str`, *optional*, defaults to `package_name`):
            The name of the repository on GitHub. In most cases, this is the same as `package_name`. However, for the `timm` library, the name is `"pytorch-image-models"` instead of `"timm"`.
    """
    page_info = {
        "version": version,
        "version_tag": version_tag,
        "language": language,
        "package_name": package_name,
        "repo_owner": repo_owner,
        "repo_name": repo_name if repo_name is not None else package_name,
    }

    read_doc_config(doc_folder)

    package = importlib.import_module(package_name) if is_python_module else None

    # Step 1: create chunks
    chunks = create_chunks(
        package,
        doc_folder,
        page_info,
        version_tag_suffix=version_tag_suffix,
        is_python_module=is_python_module,
    )

    # Step 2: create embeddings
    embeddings = call_embed_api(chunks)
    print(len(embeddings))

    # Step 3: push embeddings to vector database
    # TODO
