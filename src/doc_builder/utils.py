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

import importlib.machinery
import importlib.util
import os
import re

import yaml
from numpydoc.docscrape import NumpyDocString
from packaging import version as package_version


def update_versions_file(build_path, version):
    """
    Insert new version into _versions.yml file of the library
    Assumes that _versions.yml exists and has its first entry as master version
    """
    if version == "master":
        return
    with open(os.path.join(build_path, "_versions.yml"), "r") as versions_file:
        versions = yaml.load(versions_file, yaml.FullLoader)

        if versions[0]["version"] != "master":
            raise ValueError(f"{build_path}/_versions.yml does not contain master version")

        master_version, sem_versions = versions[0], versions[1:]
        new_version = {"version": version}
        did_insert = False
        for i, value in enumerate(sem_versions):
            if package_version.parse(new_version["version"]) == package_version.parse(value["version"]):
                # Nothing to do, the version is here already.
                return
            elif package_version.parse(new_version["version"]) > package_version.parse(value["version"]):
                sem_versions.insert(i, new_version)
                did_insert = True
                break
        if not did_insert:
            sem_versions.append(new_version)

    with open(os.path.join(build_path, "_versions.yml"), "w") as versions_file:
        versions_updated = [master_version] + sem_versions
        yaml.dump(versions_updated, versions_file)


doc_config = None


def read_doc_config(doc_folder):
    """
    Execute the `_config.py` file inside the doc source directory and executes it as a Python module.
    """
    global doc_config

    if os.path.isfile(os.path.join(doc_folder, "_config.py")):
        loader = importlib.machinery.SourceFileLoader("doc_config", os.path.join(doc_folder, "_config.py"))
        spec = importlib.util.spec_from_loader("doc_config", loader)
        doc_config = importlib.util.module_from_spec(spec)
        loader.exec_module(doc_config)


def get_doc_config():
    """
    Returns the `doc_config` if it has been loaded.
    """
    return doc_config


def convert_parametype_numpydoc_to_groupsdoc(paramtype):
    """
    Converts parameter type str that is written in numpystyle to groupsstyle (e.g. transformers docs).

    Args:
    - **paramtype** (`str`) -- The name of the object to document.

    Example::

        >>> s = "bool, optional, default True"
        >>> convert_numpydoc_to_rstdoc(s)
        '`bool`, `optional`, defults to `True`'
    """
    paramtype = re.sub(r"\s*\(.*\)$", "", paramtype).replace("default", "defults to")
    arr = paramtype.split(", ")
    for i, s in enumerate(arr):
        s = s.split(" ")
        s[-1] = f"`{s[-1]}`"
        arr[i] = " ".join(s)
    return ", ".join(arr)


def convert_numpydoc_to_groupsdoc(docstring):
    """
    Converts docstring that is written in numpystyle to groupsstyle (e.g. transformers docs).

    Args:
    - **docstring** (`str`) -- Docstring that is written in numpystyle.
    """
    numydoc = NumpyDocString(docstring)

    def helper(arr):
        """
        Helper function that joins array into space-separated string.
        """
        arr = [a.strip() for a in arr if a.strip()]
        if arr:
            return " ".join(arr) + "\n"
        return ""

    indent = "    "
    result = ""
    summary_str = f'{helper(numydoc["Summary"])}\n{helper(numydoc["Extended Summary"])}'
    result += summary_str
    if numydoc["Parameters"]:
        result += "\nArgs:\n"
        for parameter in numydoc["Parameters"]:
            result += indent + parameter[0]
            if parameter[1]:
                result += f" ({convert_parametype_numpydoc_to_groupsdoc(parameter[1])})"
            result += ":\n"
            if parameter[2]:
                result += indent * 2 + helper(parameter[2])
    if numydoc["Returns"]:
        result += "\nReturns:\n"
        for parameter in numydoc["Returns"]:
            returnttype = f":obj:'{parameter[1]}'" if parameter[1] else ""
            result += indent + ": ".join(s for s in [returnttype, helper(parameter[2])] if s)
    if numydoc["Raises"]:
        result += "\nRaises:\n"
        for parameter in numydoc["Raises"]:
            raiseerror = f"{parameter[1]}" if parameter[1] else ""
            result += indent + ": ".join(s for s in [raiseerror, helper(parameter[2])] if s)
    if numydoc["Examples"]:
        result += "\nExample::\n"
        first_line = numydoc["Examples"][0]
        indent_n = len(first_line) - len(first_line.lstrip())
        examples = [indent + line[indent_n:] for line in numydoc["Examples"]]
        examples_str = "\n".join(examples)
        result += examples_str

    return result
