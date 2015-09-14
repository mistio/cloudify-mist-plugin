import os
import unittest

from cloudify.test_utils import workflow_test


class TestPlugin(unittest.TestCase):

    @workflow_test(os.path.join('blueprint', 'blueprint.yaml'),
                   resources_to_copy=[os.path.join('blueprint',
                                                   'test_plugin.yaml')],
                   inputs={'test_input': 'new_test_input'})
    def test_install_workflow(self, cfy_local):
        """Test install workflow"""

        cfy_local.execute('install', task_retries=0)

        # extract single node instance
        instance = cfy_local.storage.get_node_instances()[0]

        # assert runtime properties is properly set in node instance
        prop = instance.runtime_properties
        print prop

        assert prop.get('ip'), "No ip set in runtime properties."
        assert prop.get('networks'), "No network set in runtime properties."

        """Test uninstall workflow"""
        cfy_local.execute('uninstall', task_retries=10)

        assert False
