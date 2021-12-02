import sys
import unittest
import tempfile
import yaml

# To find the doc_builder package.
sys.path.append("src")

from doc_builder.utils import update_versions_file


class UtilsTester(unittest.TestCase):
    def test_update_versions_file(self):
        # test canonical
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f'{tmp_dir}/_versions.yml', 'w') as tmp_yml:
                versions = [{"version": "master"}, {"version": "v4.2.3"}, {"version": "v4.2.1"}]
                yaml.dump(versions, tmp_yml)
            update_versions_file(tmp_dir, "v4.2.2")
            with open(f'{tmp_dir}/_versions.yml', 'r') as tmp_yml:
                yml_str = tmp_yml.read()
                expected_yml = '- version: master\n- version: v4.2.3\n- version: v4.2.2\n- version: v4.2.1\n'
                self.assertEqual(yml_str, expected_yml)

        # test ynl with master version only
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f'{tmp_dir}/_versions.yml', 'w') as tmp_yml:
                versions = [{"version": "master"}]
                yaml.dump(versions, tmp_yml)
            update_versions_file(tmp_dir, "v4.2.2")
            with open(f'{tmp_dir}/_versions.yml', 'r') as tmp_yml:
                yml_str = tmp_yml.read()
                expected_yml = '- version: master\n- version: v4.2.2\n'
                self.assertEqual(yml_str, expected_yml)

        # test yml without master version
        with tempfile.TemporaryDirectory() as tmp_dir:
            with open(f'{tmp_dir}/_versions.yml', 'w') as tmp_yml:
                versions = [{"version": "v4.2.2"}]
                yaml.dump(versions, tmp_yml)
            
            self.assertRaises(ValueError, update_versions_file, tmp_dir, "v4.2.2")

                
