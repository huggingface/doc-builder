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
from doc_builder.utils import update_versions_file


class UtilsTester(unittest.TestCase):
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
