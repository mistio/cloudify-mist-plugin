from os import path
import unittest

from cloudify.test_utils import workflow_test


class TestPlugin(unittest.TestCase):

    @workflow_test(path.join('blueprint', 'blueprint.yaml'),
                   resources_to_copy=[path.join('blueprint',
                                                'test_plugin.yaml')],
                   inputs={'test_input': 'new_test_input'})
    def test_my_task(self, cfy_local):
        # execute install workflow
        """

        :param cfy_local:
        """
        cfy_local.execute('install', task_retries=0)

        # extract single node instance
        instance = cfy_local.storage.get_node_instances()[0]
        print  instance
        # assert runtime properties is properly set in node instance
        cfy_local.execute('uninstall', task_retries=0)
        assert instance.runtime_properties['ip']
        
        raise AssertionError()

        ## assert deployment outputs are ok
        #self.assertDictEqual(cfy_local.outputs(),
        #                     {'test_output': 'new_test_input'})
