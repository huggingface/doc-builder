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


import tempfile
import unittest

import yaml
from doc_builder.utils import (
    convert_numpydoc_to_groupsdoc,
    convert_parametype_numpydoc_to_groupsdoc,
    update_versions_file,
)


class UtilsTester(unittest.TestCase):
    def test_convert_numpydoc_to_groupsdoc(self):
        original_numpydocstring = """Table.from_pandas(type cls, df, Schema schema=None, preserve_index=None, nthreads=None, columns=None, bool safe=True)

        Convert pandas.DataFrame to an Arrow Table.

        The column types in the resulting Arrow Table are inferred from the
        dtypes of the pandas.Series in the DataFrame. In the case of non-object
        Series, the NumPy dtype is translated to its Arrow equivalent. In the
        case of `object`, we need to guess the datatype by looking at the
        Python objects in this Series.

        Be aware that Series of the `object` dtype don't carry enough
        information to always lead to a meaningful Arrow type. In the case that
        we cannot infer a type, e.g. because the DataFrame is of length 0 or
        the Series only contains None/nan objects, the type is set to
        null. This behavior can be avoided by constructing an explicit schema
        and passing it to this function.

        Parameters
        ----------
        df : pandas.DataFrame
        schema : pyarrow.Schema, optional
            The expected schema of the Arrow Table. This can be used to
            indicate the type of columns if we cannot infer it automatically.
            If passed, the output will have exactly this schema. Columns
            specified in the schema that are not found in the DataFrame columns
            or its index will raise an error. Additional columns or index
            levels in the DataFrame which are not specified in the schema will
            be ignored.
        preserve_index : bool, optional, default True
            Whether to store the index as an additional column in the resulting
            ``Table``. The default of None will store the index as a column,
            except for RangeIndex which is stored as metadata only. Use
            ``preserve_index=True`` to force it to be stored as a column.
        nthreads : int, default None (may use up to system CPU count threads)
            If greater than 1, convert columns to Arrow in parallel using
            indicated number of threads.
        columns : list, optional
           List of column to be converted. If None, use all columns.
        safe : bool, default True
           Check for overflows or other unsafe conversions.

        Raises
        ------
        KeyError
            If any of the passed columns name are not existing.
        ValueError

        Returns
        -------
        Table
            New table without the columns.

        Examples
        --------

        >>> import pandas as pd
        >>> import pyarrow as pa
        >>> df = pd.DataFrame({
            ...     'int': [1, 2],
            ...     'str': ['a', 'b']
            ... })
        >>> pa.Table.from_pandas(df)
        <pyarrow.lib.Table object at 0x7f05d1fb1b40>"""

        expected_conversion = """Convert pandas.DataFrame to an Arrow Table.

The column types in the resulting Arrow Table are inferred from the dtypes of the pandas.Series in the DataFrame. In the case of non-object Series, the NumPy dtype is translated to its Arrow equivalent. In the case of `object`, we need to guess the datatype by looking at the Python objects in this Series. Be aware that Series of the `object` dtype don't carry enough information to always lead to a meaningful Arrow type. In the case that we cannot infer a type, e.g. because the DataFrame is of length 0 or the Series only contains None/nan objects, the type is set to null. This behavior can be avoided by constructing an explicit schema and passing it to this function.

Args:
    df (:obj:`pandas.DataFrame`):
    schema (:obj:`pyarrow.Schema`, `optional`): The expected schema of the Arrow Table. This can be used to indicate the type of columns if we cannot infer it automatically. If passed, the output will have exactly this schema. Columns specified in the schema that are not found in the DataFrame columns or its index will raise an error. Additional columns or index levels in the DataFrame which are not specified in the schema will be ignored.
    preserve_index (:obj:`bool`, `optional`, defaults to :obj:`True`): Whether to store the index as an additional column in the resulting ``Table``. The default of None will store the index as a column, except for RangeIndex which is stored as metadata only. Use ``preserve_index=True`` to force it to be stored as a column.
    nthreads (:obj:`int`, defaults to :obj:`None`): If greater than 1, convert columns to Arrow in parallel using indicated number of threads.
    columns (:obj:`list`, `optional`): List of column to be converted. If None, use all columns.
    safe (:obj:`bool`, defaults to :obj:`True`): Check for overflows or other unsafe conversions.

Returns:
    :obj:`Table`: New table without the columns.

Raises:
    KeyError: If any of the passed columns name are not existing.
    ValueError

Example::
    >>> import pandas as pd
    >>> import pyarrow as pa
    >>> df = pd.DataFrame({
        ...     'int': [1, 2],
        ...     'str': ['a', 'b']
        ... })
    >>> pa.Table.from_pandas(df)
    <pyarrow.lib.Table object at 0x7f05d1fb1b40>"""

        self.assertEqual(convert_numpydoc_to_groupsdoc(original_numpydocstring), expected_conversion)

    def test_convert_parametype_numpydoc_to_groupsdoc(self):
        # test canonical
        original_numpydocstring = "bool, optional, default True"
        expected_conversion = ":obj:`bool`, `optional`, defaults to :obj:`True`"
        self.assertEqual(convert_parametype_numpydoc_to_groupsdoc(original_numpydocstring), expected_conversion)

        # test without `optional`
        original_numpydocstring = "bool, default True"
        expected_conversion = ":obj:`bool`, defaults to :obj:`True`"
        self.assertEqual(convert_parametype_numpydoc_to_groupsdoc(original_numpydocstring), expected_conversion)

        # test with extra info
        original_numpydocstring = "bool, optional, default True (some extra info)"
        expected_conversion = ":obj:`bool`, `optional`, defaults to :obj:`True`"
        self.assertEqual(convert_parametype_numpydoc_to_groupsdoc(original_numpydocstring), expected_conversion)

        # test int
        original_numpydocstring = "int, optional, default 1"
        expected_conversion = ":obj:`int`, `optional`, defaults to 1"
        self.assertEqual(convert_parametype_numpydoc_to_groupsdoc(original_numpydocstring), expected_conversion)

        # test str
        original_numpydocstring = "str, optional, default 'some_str'"
        expected_conversion = ":obj:`str`, `optional`, defaults to :obj:`'some_str'`"
        self.assertEqual(convert_parametype_numpydoc_to_groupsdoc(original_numpydocstring), expected_conversion)

    def test_update_versions_file(self):
        # test canonical
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/_versions.yml", "w") as tmp_yml:
                versions = [{"version": "master"}, {"version": "v4.2.3"}, {"version": "v4.2.1"}]
                yaml.dump(versions, tmp_yml)
            update_versions_file(tmp_dir, "v4.2.2")
            with open(f"{tmp_dir}/_versions.yml", "r") as tmp_yml:
                yml_str = tmp_yml.read()
                expected_yml = "- version: master\n- version: v4.2.3\n- version: v4.2.2\n- version: v4.2.1\n"
                self.assertEqual(yml_str, expected_yml)

        # test yml with master version only
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/_versions.yml", "w") as tmp_yml:
                versions = [{"version": "master"}]
                yaml.dump(versions, tmp_yml)
            update_versions_file(tmp_dir, "v4.2.2")
            with open(f"{tmp_dir}/_versions.yml", "r") as tmp_yml:
                yml_str = tmp_yml.read()
                expected_yml = "- version: master\n- version: v4.2.2\n"
                self.assertEqual(yml_str, expected_yml)

        # test yml without master version
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/_versions.yml", "w") as tmp_yml:
                versions = [{"version": "v4.2.2"}]
                yaml.dump(versions, tmp_yml)

            self.assertRaises(ValueError, update_versions_file, tmp_dir, "v4.2.2")

        # test inserting duplicate version into yml
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f"{tmp_dir}/_versions.yml", "w") as tmp_yml:
                versions = [{"version": "master"}]
                yaml.dump(versions, tmp_yml)
            update_versions_file(tmp_dir, "v4.2.2")
            update_versions_file(tmp_dir, "v4.2.2")  # inserting duplicate version
            with open(f"{tmp_dir}/_versions.yml", "r") as tmp_yml:
                yml_str = tmp_yml.read()
                expected_yml = "- version: master\n- version: v4.2.2\n"
                self.assertEqual(yml_str, expected_yml)
