import os
import unittest

from cloudify.test_utils import workflow_test
from time import sleep


class TestPlugin(unittest.TestCase):

    @workflow_test(os.path.join('blueprint', 'blueprint.yaml'),
                   resources_to_copy=[os.path.join('blueprint',
                                                   'test_plugin.yaml')],
                   inputs={'api_token': "df94cf8ca00e8f9b4d3873c4c9bd35f6854783438e66478819c8b7f91c5c4a37",
                           'mist_uri': "http://172.17.0.1",
                           'cloud_id': "c204bf73f65544b1b63c83b16373660a",
                           'key_id': "hello2",
                           'image_id': "d69e1f0e-5205-4698-880e-81f95774a633",
                           'size_id': "1",
                           'disk': "1",
                           'machine_name': "happesd"

                           }
                   )
    def test_install_workflow(self, cfy_local):
        """Test install workflow"""

        cfy_local.execute('install', task_retries=0)

        # extract single node instance
        for instance in cfy_local.storage.get_node_instances():
            prop = instance.runtime_properties
            if prop.get("mist_type") == "machine":
                assert prop.get('ip'), "No ip set in runtime properties."
                assert prop.get('networks'), "No network set in runtime properties."
                break
        # instance = cfy_local.storage.get_node_instances()[1]
        # assert runtime properties is properly set in node instance
        # print(prop)

        # assert prop.get('private_key_path'), "No private key path set in runtime properties."
        """Test uninstall workflow"""
        # cfy_local.execute('uninstall', task_retries=10)

        # assert False