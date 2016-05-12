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
                           'cloud_id': "492f3ad72ebe4b27b21f83b93e96b2d1",
                           'key_id': "hello2",
                           'image_id': "ami-a21529cc",
                           'size_id': "t1.micro",
                           'location_id': "ap-northeast-1a",
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
                break
        # instance = cfy_local.storage.get_node_instances()[1]
        # assert runtime properties is properly set in node instance
        print(prop)

        assert prop.get('ip'), "No ip set in runtime properties."
        assert prop.get('networks'), "No network set in runtime properties."
        # assert prop.get('private_key_path'), "No private key path set in runtime properties."
        """Test uninstall workflow"""
        cfy_local.execute('uninstall', task_retries=10)

        # assert False