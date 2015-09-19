
# Built-in Imports
import os


from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.decorators import operation
import connection


@operation
def creation_validation(**_):
    """ This validates all nodes before bootstrap.
    """

    key_file = _get_path_to_key_file()
    key_file_in_filesystem = _search_for_key_file(key_file)

    if ctx.node.properties['use_external_resource']:
        if not key_file_in_filesystem:
            raise NonRecoverableError(
                'External resource, but the key file does not exist locally.')
        try:
            _get_key_pair_by_id(ctx.node.properties['resource_id'])
        except NonRecoverableError as e:
            raise NonRecoverableError(
                'External resource, '
                'but the key pair does not exist in the account: '
                '{0}'.format(str(e)))
    else:
        if key_file_in_filesystem:
            raise NonRecoverableError(
                'Not external resource, '
                'but the key file exists locally.')
        try:
            _get_key_pair_by_id(ctx.node.properties['resource_id'])
        except NonRecoverableError:
            pass
        else:
            raise NonRecoverableError(
                'Not external resource, '
                'but the key pair exists in the account.')


@operation
def create(**kwargs):
    """Creates a keypair."""

    mist_client = connection.MistConnectionClient().client

    if _create_external_keypair():
        return

    key_pair_name = get_resource_id()

    ctx.logger.debug('Attempting to create key pair.')

    private = mist_client.generate_key()
    mist_client.add_key(key_name=key_pair_name, private=private)
    mist_client.update_keys()
    kp = mist_client.keys(search=key_pair_name)[0]
    # try:
    # except:
    #     raise NonRecoverableError('Key pair not created. ')
    #     ctx.instance.runtime_properties["mist_resource_id"] = kp.id
    _save_key_pair(kp)


@operation
def delete(**kwargs):
    """Deletes a keypair."""

    mist_client = connection.MistConnectionClient().client

    key_pair_name = get_external_resource_id_or_raise(
        'delete key pair')

    if _delete_external_keypair():
        return

    ctx.logger.debug('Attempting to delete key pair from account.')

    try:
        mist_client.keys(search=key_pair_name)[0].delete()
    except e:
        raise NonRecoverableError('{0}'.format(str(e)))

    unassign_runtime_property_from_resource('mist_resource_id')
    _delete_key_file()
    ctx.logger.info('Deleted key pair: {0}.'.format(key_pair_name))


def _create_external_keypair():
    """If use_external_resource is True, this will set the runtime_properties,
    and then exit.
    :param ctx: The Cloudify context.
    :return False: Cloudify resource. Continue operation.
    :return True: External resource. Set runtime_properties. Ignore operation.
    :raises NonRecoverableError: If unable to locate the existing key file.
    """
    print "create external keypair"
    if not use_external_resource(ctx.node.properties):
        return False

    key_pair_name = ctx.node.properties['resource_id']
    key_pair_in_account = _get_key_pair_by_id(key_pair_name)
    key_path_in_filesystem = _get_path_to_key_file()
    ctx.logger.debug(
        'Path to key file: {0}.'.format(key_path_in_filesystem))
    if not key_pair_in_account:
        raise NonRecoverableError(
            'External resource, but the key pair is not in the account.')
    if not _search_for_key_file(key_path_in_filesystem):
        raise NonRecoverableError(
            'External resource, but the key file does not exist.')
    set_external_resource_id(key_pair_name)
    return True


def _delete_external_keypair():
    """If use_external_resource is True, this will delete the runtime_properties,
    and then exit.
    :param ctx: The Cloudify context.
    :return False: Cloudify resource. Continue operation.
    :return True: External resource. Unset runtime_properties.
        Ignore operation.
    """

    if not use_external_resource(ctx.node.properties):
        return False

    ctx.logger.info('External resource. Not deleting keypair.')
    unassign_runtime_property_from_resource(
        "mist_resource_id")
    return True


def _delete_key_file():
    """ Deletes the key pair in the file specified in the blueprint.
    :param ctx: The Cloudify context.
    :raises NonRecoverableError: If unable to delete the local key file.
    """

    key_path = _get_path_to_key_file()

    if _search_for_key_file(key_path):
        try:
            os.remove(key_path)
        except OSError as e:
            raise NonRecoverableError(
                'Unable to delete key pair: {0}.'
                .format(str(e)))


def _save_key_pair(key_pair_object):
    """Saves a keypair to the filesystem.
    :param key_pair_object: The key pair object as returned from create.
    :param ctx: The Cloudify Context.
    :raises NonRecoverableError: If private_key_path node property not set.
    :raises NonRecoverableError: If Unable to save key file locally.
    """

    ctx.logger.debug('Attempting to save the key_pair_object.')

    if not key_pair_object.private:
        raise NonRecoverableError(
            'Cannot save key. KeyPair contains no private key.')

    file_path = _get_path_to_key_file()
    if os.path.exists(file_path):
        raise NonRecoverableError(
            '{0} already exists, it will not be overwritten.'.format(
                file_path))
    fp = open(file_path, 'wb')
    fp.write(key_pair_object.private)
    fp.close()

    _set_key_file_permissions(file_path)


def _set_key_file_permissions(key_file):

    if os.access(key_file, os.W_OK):
        os.chmod(key_file, 0o600)
    else:
        ctx.logger.error(
            'Unable to set permissions key file: {0}.'.format(key_file))


def _get_key_pair_by_id(key_pair_id):
    """Returns the key pair object for a given key pair id.
    :param key_pair_id: The ID of a keypair.
    :returns The mist keypair object.
    :raises NonRecoverableError: If Mist finds no matching key pairs.
    """
    mist_client = connection.MistConnectionClient().client

    try:
        key_pairs = mist_client.keys(search=key_pair_id)
    except e:
        raise NonRecoverableError('{0}'.format(str(e)))

    return key_pairs[0] if key_pairs else None


def _get_path_to_key_file():
    """Gets the path to the key file.
    :param ctx: The Cloudify context.
    :returns key_path: Path to the key file.
    :raises NonRecoverableError: If private_key_path is not set.
    """

    if 'private_key_path' not in ctx.node.properties:
        raise NonRecoverableError(
            'Unable to get key file path, private_key_path not set.')

    return os.path.expanduser(ctx.node.properties['private_key_path'])


def _search_for_key_file(path_to_key_file):
    """ Checks if the key_path exists in the local filesystem.
    :param key_path: The path to the key pair file.
    :return boolean if key_path exists (True) or not.
    """

    return True if os.path.exists(path_to_key_file) else False


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


def get_external_resource_id_or_raise(operation):
    """Checks if the EXTERNAL_RESOURCE_ID runtime_property is set and returns it.
    :param operation: A string representing what is happening.
    :param ctx_instance: The CTX Node-Instance Context.
    :param ctx:  The Cloudify ctx context.
    :returns The EXTERNAL_RESOURCE_ID runtime_property for a CTX Instance.
    :raises NonRecoverableError: If EXTERNAL_RESOURCE_ID has not been set.
    """

    ctx.logger.debug(
        'Checking if {0} in instance runtime_properties, for {0} operation.'
        .format("mist_resource_id", operation))

    if "mist_resource_id" not in ctx.instance.runtime_properties:
        raise NonRecoverableError(
            'Cannot {0} because {1} is not assigned.'
            .format(operation, "mist_resource_id"))

    return ctx.instance.runtime_properties["mist_resource_id"]


def unassign_runtime_property_from_resource(property_name):
    """Pops a runtime_property and reports to debug.
    :param property_name: The runtime_property to remove.
    :param ctx_instance: The CTX Node-Instance Context.
    :param ctx:  The Cloudify ctx context.
    """

    value = ctx.instance.runtime_properties.pop(property_name)
    ctx.logger.debug(
        'Unassigned {0} runtime property: {1}'.format(property_name, value))


def is_external_resource(properties):
    return is_external_resource_by_properties(properties)

def is_external_resource_by_properties(properties):
    return 'use_external_resource' in properties and \
        properties['use_external_resource']

def use_external_resource(properties):
    if not properties.get('use_external_resource'):
        return None

    if not "resource_id" in properties or not properties["resource_id"]:
        raise NonRecoverableError(
            'External resource, but resource not set.')
    ctx.logger.debug(
        'Resource Id: {0}'.format(properties["resource_id"]))    
    return True
        


def set_external_resource_id(value):
    """Sets the EXTERNAL_RESOURCE_ID runtime_property for a Node-Instance.
    """
    ctx.instance.runtime_properties["mist_resource_id"] = value
       