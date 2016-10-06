import os

import string
from random import choice

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError
from mistclient import MistClient

def get_resource_id():
    """Returns the resource id, if the user doesn't provide one,
    this will create one for them.
    :param node_properties: The node properties dictionary.
    :return resource_id: A string.
    """

    if ctx.node.properties['resource_id']:
        return ctx.node.properties['resource_id']
    elif 'private_key_path' in ctx.node.properties:
        directory_path, filename = \
            os.path.split(ctx.node.properties['private_key_path'])
        resource_id, filetype = filename.split('.')
        return resource_id

    return '{0}-{1}'.format(ctx.deployment.id, ctx.instance.id)


def generate_name():
    """
    Generate a random name for a newly provisioned machine
    """
    def random_chars():
        return ''.join(choice(string.letters + string.digits) for _ in range(4))

    return 'MistCfyNode-%s-%s' % (random_chars(), random_chars())

