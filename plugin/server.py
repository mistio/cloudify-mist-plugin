import time

from plugin import utils
from plugin import constants
from plugin import connection

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError


@operation
def creation_validation(**_):
    """ This checks that all user supplied info is valid """
    ctx.logger.info('Checking validity of info')
    mist_client = connection.MistConnectionClient()
    try:
        client = mist_client.client
    except:
        raise NonRecoverableError('Credentials failed')

    for property_key in constants.INSTANCE_REQUIRED_PROPERTIES:
        if property_key not in ctx.node.properties:
            raise NonRecoverableError(
                '{0} is a required input. Unable to create.'.format(property_key))
    cloud = client.clouds(id=ctx.node.properties['cloud_id'])
    if not len(cloud):
        raise NonRecoverableError(
            '{0} cloud was not found.'.format(ctx.node.properties['cloud_id']))
    image = ""
    for im in cloud[0].images:
        if im[id] == ctx.node.properties['image_id']:
            image = im
            break
    if not image:
        raise NonRecoverableError(
            'image_id {0} not found.'.format(ctx.node.properties['image_id']))
    size = ""
    for si in cloud[0].sizes:
        if si[id] == ctx.node.properties['size_id']:
            size = si
            break
    if not size:
        raise NonRecoverableError(
            'size_id {0} not found.'.format(ctx.node.properties['size_id']))
    location = ""
    for lo in cloud[0].locations:
        if lo[id] == ctx.node.properties['location_id']:
            location = lo
            break
    if not location:
        raise NonRecoverableError(
            'location_id {0} not found.'.format(ctx.node.properties['location_id']))

    # FIXME this should not always raise a NonRecoverableError
    machine_name = ctx.node.properties.get('name', '')
    if machine_name:
        machines = cloud[0].machines(search=machine_name)
        if ctx.node.properties['use_external_resource'] and not len(machines):
            raise NonRecoverableError('Machine {0} not found.'.format(machine_name))
        if not ctx.node.properties['use_external_resource'] and len(machines):
            raise NonRecoverableError('Machine {0} exists.'.format(machine_name))
        if ctx.node.properties['use_external_resource'] and len(machines):
            if machines[0].info["state"] == "running":
                pass
            elif machines[0].info["state"] == "stopped":
                try:
                    machines[0].start()
                except:
                    pass
                delay = 0
                while True:
                    time.sleep(10)
                    cloud[0].update_machines()
                    if cloud[0].machines(search=machine_name)[0].info["state"] == "running":
                        break
                    elif delay == 5:
                        raise NonRecoverableError(
                            'Machine {0} in stopped state.'.format(machine_name)
                        )
                    delay += 1
            else:
                raise NonRecoverableError(
                    'Machine {0} error state.'.format(machine_name))


def create_machine(properties, skip_post_deploy_validation=False, **kwargs):
    """Create a machine with the given parameters by invoking the MistClient

    The `properties` must include all parameters required for the machine's
    creation. These parameters are supposed to be populated mainly by the
    blueprint's inputs. In the simplest scenario, `properties` should be
    equal to `ctx.node.properties`. But, they can also be modified before
    passed into this method.

    Similarly, `kwargs` correspond to a specific operation's inputs and they
    should be used likewise, even if this method is not invoked directly by
    the blueprint's lifecycle operation, but rather from another method, such
    as user-defined workflow.

    """
    stack_name = utils.get_stack_name()
    node_type = kwargs.get('node_type', 'instance')

    conn = connection.MistConnectionClient()

    # The job_id associated with the current workflow.
    job_id = conn.job_id

    params = properties['parameters']

    if properties['use_external_resource']:
        cloud_id = get_cloud_id(properties)
        machine_id = get_machine_id(properties)
        cloud = conn.get_cloud(cloud_id)
        ctx.instance.runtime_properties['machine_id'] = str(machine_id)
        ctx.instance.runtime_properties['use_external_resource'] = True
    else:
        # Get the cloud on which to provision the new machines.
        cloud_id = params.pop('cloud_id')
        cloud = conn.get_cloud(cloud_id)

        try:
            name = (
                params.pop('name', '') or  # Get or auto-generate.
                utils.generate_name(stack_name, node_type)
            )
            key = params.pop('key') or ''  # Avoid None.
            size_id = params.pop('size_id')
            image_id = params.pop('image_id')
            location_id = params.pop('location_id')
            job = cloud.create_machine(name, key, image_id, location_id,
                                       size_id, async=True, **params)
        except Exception as exc:
            raise NonRecoverableError(exc)

        # Wait for machine creation to finish.
        event = utils.wait_for_event(
            job_id=job['job_id'],
            job_kwargs={
                'action': 'machine_creation_finished',
                'machine_name': name
            },
            timeout=600
        )
        ctx.instance.runtime_properties['machine_id'] = event['machine_id']
        ctx.instance.runtime_properties['use_external_resource'] = False

        # Wait for machine's post-deploy configuration to finish.
        if key and not skip_post_deploy_validation:
            event = utils.wait_for_event(
                job_id=job['job_id'],
                job_kwargs={
                    'action': 'post_deploy_finished',
                    'machine_id': event['machine_id'],
                }
            )

    # Update the node instance's runtime properties.
    machine_id = ctx.instance.runtime_properties['machine_id']
    machine = conn.get_machine(cloud_id, machine_id)

    ctx.instance.runtime_properties['job_id'] = job_id
    ctx.instance.runtime_properties['machine_name'] = machine.name

    ctx.instance.runtime_properties['info'] = machine.info
    ctx.instance.runtime_properties['cloud_id'] = cloud_id
    ctx.instance.runtime_properties['mist_type'] = 'machine'


@operation
def create(**kwargs):
    node_properties = ctx.node.properties.copy()
    create_machine(node_properties, **kwargs)


@operation
def start(**_):
    try:
        conn = connection.MistConnectionClient()
        machine = conn.get_machine(
            cloud_id=ctx.instance.runtime_properties['cloud_id'],
            machine_id=ctx.instance.runtime_properties['machine_id']
        )
        machine.start()
    except Exception as exc:
        ctx.logger.error('Failed to start machine. %s', exc)

    # FIXME 1) This is not currently used. 2) Should it be here? 3) This
    # should probably be passed to the create_machine method.
    # if ctx.node.properties.get("monitoring"):
    #     connection.MistConnectionClient().machine.enable_monitoring()
    #     ctx.logger.info('Monitoring enabled')


@operation
def stop(**_):
    try:
        conn = connection.MistConnectionClient()
        machine = conn.get_machine(
            cloud_id=ctx.instance.runtime_properties['cloud_id'],
            machine_id=ctx.instance.runtime_properties['machine_id']
        )
        machine.stop()
    except Exception as exc:
        ctx.logger.error('Failed to stop machine. %s', exc)


@operation
def delete(**_):
    if not ctx.instance.runtime_properties.get('use_external_resource'):
        try:
            conn = connection.MistConnectionClient()
            machine = conn.get_machine(
                cloud_id=ctx.instance.runtime_properties['cloud_id'],
                machine_id=ctx.instance.runtime_properties['machine_id']
            )
            machine.destroy()
        except Exception as exc:
            ctx.logger.error('Failed to destroy machine. %s', exc)
    else:
        ctx.logger.info('use_external_resource flag is true, cannot delete.')


@operation
def run_script(**kwargs):
    conn = connection.MistConnectionClient()
    machine = conn.get_machine(
        cloud_id=ctx.instance.runtime_properties['cloud_id'],
        machine_id=ctx.instance.runtime_properties['machine_id']
    )
    kwargs['cloud_id'] = machine.cloud.id
    kwargs['machine_id'] = str(machine.id)
    script_params = kwargs.pop("params", "")
    kwargs.pop('ctx', None)
    if kwargs.get("script_id", ''):
        try:
            job_id = conn.client.run_script(**kwargs)
        except Exception as exc:
            raise NonRecoverableError(exc)
    else:
        try:
            response = conn.client.add_and_run_script(
                machine.cloud.id, script_params=script_params,
                fire_and_forget=False, **kwargs
            )
        except Exception as exc:
            raise NonRecoverableError(exc)


def get_cloud_id(properties=None):
    """Return the cloud id of the current execution thread

    The search is performed against the current node's properties. Another
    properties dict may be optionally passed to this method, which will be
    used instead of `ctx.node.properties`. Note that passing a custom dict
    of properties is meant for advanced use cases, such as overriding the
    immutable, built-in `ctx.node.properties`, and SHOULD NOT be opted for.

    Note that this method does not take into account the runtime properties
    of the current node instance, while searching for the cloud_id. If one
    wants to search the runtime properties, then he should do so explicitly
    outside this method.

    This method SHOULD be primarily invoked during the early stages of the
    install workflow, such as the `create_machine` operation, in order to
    discover the cloud_id of the resource in the current execution thread,
    whether the resource is external or not. Down the road, it is advised
    that the `ctx.instance.runtime_properties` dict is used to look-up the
    corresponding resource identifiers. For instance, the `create_machine`
    operation *always* adds the following two properties:

        ctx.instance.runtime_properties['cloud_id']
        ctx.instance.runtime_properties['machine_id']

    Thus, in lifecycle operations other than the `create` operation of the
    install workflow, one SHOULD use the aforementioned runtime properties
    instead of invoking this method.

    If no cloud_id can be found, then a `NonRecoverableError` will be raised.

    """
    properties = properties or ctx.node.properties

    # If the resource does not already exist, then search its node properties.
    if not utils.is_resource_external(properties):
        cloud_id = properties.get('parameters', {}).get('cloud_id')
        if not cloud_id:
            raise NonRecoverableError('cloud_id missing from node properties')
        return cloud_id

    # If the resource exists, then get its `resource_id`. The following method
    # will raise an exception, if the resource of the current execution thread
    # is not external.
    resource_id = utils.get_external_resource_id(properties)
    ctx.logger.info('Looking for cloud_id of existing machine %s', resource_id)

    if isinstance(resource_id, (basestring, int)):
        cloud_id = properties.get('parameters', {}).get('cloud_id')
        if not cloud_id:
            raise NonRecoverableError('cloud_id missing from node properties')
        return str(cloud_id)

    if isinstance(resource_id, dict):
        cloud_id = resource_id.get('cloud_id')
        if not cloud_id:
            raise NonRecoverableError('Failed to get cloud_id %s', resource_id)
        return str(cloud_id)

    raise NonRecoverableError('Could not find cloud_id')


def get_machine_id(properties=None):
    """Return the machine id of the current execution thread

    The search is performed against the current node's properties. Another
    properties dict may be optionally passed to this method, which will be
    used instead of `ctx.node.properties`. Note that passing a custom dict
    of properties is meant for advanced use cases, such as overriding the
    immutable, built-in `ctx.node.properties`, and SHOULD NOT be opted for.

    Note that this method does not take into account the runtime properties
    of the current node instance, while searching for a machine_id. If one
    wants to search the runtime properties, then he should do so explicitly
    outside this method.

    This method SHOULD be primarily invoked during the early stages of the
    install workflow, such as the `create_machine` operation, in order to
    discover the EXTERNAL machine_id in the current execution thread. This
    method SHOULD NOT be used unless the resource is external since the id
    of a machine will not be available until the `create` operation is done.

    Down the road, it is advised that the `ctx.instance.runtime_properties`
    dict is used to look-up the corresponding resource identifiers instead.
    The `create_machine` operation *always* adds the following two properties:

        ctx.instance.runtime_properties['cloud_id']
        ctx.instance.runtime_properties['machine_id']

    Thus, in lifecycle operations other than the `create` operation of the
    install workflow, one SHOULD use the aforementioned runtime properties
    instead of invoking this method.

    If no machine_id is found, then a `NonRecoverableError` will be raised.

    """
    properties = properties or ctx.node.properties

    if not utils.is_resource_external(properties):
        raise NonRecoverableError('Cannot get id of non-external machine')

    resource_id = utils.get_external_resource_id(properties)
    ctx.logger.info('Looking for machine_id in resource_id %s', resource_id)

    if isinstance(resource_id, (basestring, int)):
        return str(resource_id)

    if isinstance(resource_id, dict):
        return str(resource_id.get('machine_id'))

    raise NonRecoverableError('Could not find machine_id')
