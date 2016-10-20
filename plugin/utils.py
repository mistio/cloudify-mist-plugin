from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError

import os
import glob
import json

import string
import random

from mistclient import MistClient

from constants import STORAGE


class LocalStorage(object):
    """
    LocalStorage gives full access to a node instance's properties by reading
    the instance object directly from file

    This class is meant to be called as such:

        node_instance = LocalStorage.get('kube_master')

    where `kube_master` is the actual node_instance as defined in the
    respective blueprint. In order to access the runtime properties simply call:

        node_instance.runtime_properties

    which will return the dict of all of the instance's runtime properties
    """
    def __init__(self, node):
        """
        Searches in local-storage for the file that corresponds to the node
        instance provided
        """
        instance_file = self.fetch_instance_file(node)
        with open(instance_file, 'r') as _instance:
            instance_from_file = _instance.read()

        self.instance_from_file = json.loads(instance_from_file)

    @classmethod
    def get(cls, node):
        """
        A class method to initiate the LocalStorage with the specified node
        """
        node = cls(node)
        return node

    @property
    def runtime_properties(self):
        """
        Returns the node instance's runtime properties in a way similiar to
        `ctx`
        """
        return self.instance_from_file['runtime_properties']

    def fetch_instance_file(self, node):
        """
        Tries to discover the path of local-storage in order to fetch the
        required node instance
        """
        local_storage = os.path.join('/tmp/templates',
                                     'mistio-kubernetes-blueprint-[A-Za-z0-9]*',
                                     STORAGE % node)
        local_storage = glob.glob(local_storage)
        if local_storage:
            node_file = local_storage[0]
        # TODO: Well, this is weird, but the local-storage exists on a different
        # path in case a user executes `cfy local` directly from his terminal
        else:
            if not os.path.exists(os.path.join('..', STORAGE % node)):
                raise Exception('Failed to locate local-storage')
            node_file = os.path.join('..', STORAGE % node)
        return node_file


def get_resource_id():
    """
    Returns the a resource's ID. If the user doesn't provide one, this method
    will create one instead
    :param node_properties: The node properties dictionary
    :return resource_id: A string
    """

    if ctx.node.properties['resource_id']:
        return ctx.node.properties['resource_id']
    elif 'private_key_path' in ctx.node.properties:
        directory_path, filename = os.path.split(ctx.node.properties[
                                                  'private_key_path'])
        resource_id, filetype = filename.split('.')
        return resource_id

    return '{0}-{1}'.format(ctx.deployment.id, ctx.instance.id)


def generate_name(length=4):
    """Generate a random name for a newly provisioned machine"""
    ret = 'mistcfynode-%s-%s' % (random_string(length), random_string(length))
    return ret.lower()


def random_string(length=6):
    """Generate a random alphanumeric string. Default length is set to 4"""
    _chars = string.letters + string.digits
    return ''.join(random.choice(_chars) for _ in range(length))


def get_job_id():
    """
    Read the Stack's original job ID from file in order to create nested logs
    """
    try:
        with open('/tmp/cloudify-mist-plugin-job', 'r') as jf:
            job_id = jf.read()
    except IOError as err:
        job_id = ''
        ctx.logger.debug(err)
    return job_id

