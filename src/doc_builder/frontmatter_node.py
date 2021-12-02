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


import yaml


class FrontmatterNode:
    """
    A helper class that is used in generating frontmatter for mdx files.

    This class is a typical graph node class, which allows it to model
    markdown header hierarchy (i.e. h2 belongs to h1 above it).
    """

    def __init__(self, title, local):
        self.title = title
        self.local = local
        self.children = []

    def add_child(self, child, header_level):
        parent = self
        nested_level = header_level - 2
        while nested_level:
            if not parent.children:
                parent.children.append(FrontmatterNode(None, None))
            parent = parent.children[-1]
            nested_level -= 1
        parent.children.append(child)

    def get_frontmatter(self):
        self._remove_null_nodes()
        frontmatter_yaml = yaml.dump(self._dictionarify(), allow_unicode=True).replace("\\U0001F917", "🤗")
        return f"---\n{frontmatter_yaml}---\n"

    def _remove_null_nodes(self):
        if len(self.children) == 1 and self.children[0].title is None:
            child_children = self.children[0].children
            self.children = child_children
        for section in self.children:
            section._remove_null_nodes()

    def _dictionarify(self):
        if not self.children:
            return {"title": self.title, "local": self.local}
        children = [section._dictionarify() for section in self.children]
        return {"title": self.title, "local": self.local, "sections": children}
