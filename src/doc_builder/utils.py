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
    paramtype (`str`): The name of the object to document.

    Example:
    ```py
    >>> s = "bool, optional, default True"
    >>> convert_numpydoc_to_rstdoc(s)
    ':obj:`bool`, `optional`, defaults to :obj:`True`'
    ```
    """
    paramtype = re.sub(r"\s*\(.*\)$", "", paramtype).replace("default", "defaults to")
    arr = paramtype.split(", ")
    for i, s in enumerate(arr):
        s = s.split(" ")
        if "optional" in s[-1]:
            # parameter is optional or not
            s[-1] = f"`{s[-1]}`"
        elif "defaults" in s:
            # parameter default value
            valtype = type(eval(s[-1]))
            non_obj_types = [int, float]
            s[-1] = s[-1] if valtype in non_obj_types else f":obj:`{s[-1]}`"
        else:
            # parameter type
            s[-1] = f":obj:`{s[-1]}`"
        arr[i] = " ".join(s)
    return ", ".join(arr)


def convert_numpydoc_to_groupsdoc(docstring):
    """
    Converts docstring that is written in numpystyle to groupsstyle (e.g. transformers docs).

    Args:
    - **docstring** (`str`) -- Docstring that is written in numpystyle.
    """

    def stringify_arr(arr):
        """
        Helper function that joins array into space-separated string.
        """
        arr = [a.strip() for a in arr if a.strip()]
        if arr:
            return " ".join(arr) + "\n"
        return ""

    def start_section(docstring, section):
        """
        Helper function that joins array into space-separated string.
        """
        return docstring.rstrip() + f"\n\n{section}:\n"

    numydoc = NumpyDocString(docstring)
    indent = "    "
    result = ""
    summary_str = f'{stringify_arr(numydoc["Summary"])}\n{stringify_arr(numydoc["Extended Summary"])}'
    result += summary_str
    if numydoc["Parameters"]:
        result = start_section(result, "Args")
        for parameter in numydoc["Parameters"]:
            result = result.rstrip() + "\n"
            result += indent + parameter[0]
            if parameter[1]:
                result += f" ({convert_parametype_numpydoc_to_groupsdoc(parameter[1])}):"
            if parameter[2]:
                result += " " + stringify_arr(parameter[2])
    if numydoc["Returns"]:
        result = start_section(result, "Returns")
        for parameter in numydoc["Returns"]:
            returnttype = f":obj:`{parameter[1]}`" if parameter[1] else ""
            result += indent + ": ".join(s for s in [returnttype, stringify_arr(parameter[2])] if s)
    if numydoc["Yields"]:
        result = start_section(result, "Yields")
        for parameter in numydoc["Yields"]:
            returnttype = f":obj:`{parameter[1]}`" if parameter[1] else ""
            result += indent + ": ".join(s for s in [returnttype, stringify_arr(parameter[2])] if s)
    if numydoc["Raises"]:
        result = start_section(result, "Raises")
        for parameter in numydoc["Raises"]:
            result = result.rstrip() + "\n"
            raiseerror = f"{parameter[1]}" if parameter[1] else ""
            result += indent + ": ".join(s for s in [raiseerror, stringify_arr(parameter[2])] if s)
    if numydoc["Examples"]:
        result = start_section(result, "Example:")
        first_line = numydoc["Examples"][0]
        indent_n = len(first_line) - len(first_line.lstrip())
        examples = [indent + line[indent_n:] for line in numydoc["Examples"]]
        examples_str = "\n".join(examples)
        result += examples_str

    return result
