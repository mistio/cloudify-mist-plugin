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
    """Create a machine with the given parameters by invoking the MistClient.

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

    mist_client = connection.MistConnectionClient()
    try:
        client = mist_client.client
    except:
        raise NonRecoverableError('User authentication failed')

    params = properties['parameters']
    cloud_id = params.pop('cloud_id')
    cloud = client.clouds(id=cloud_id)[0]

    # # TODO Decide how to handle this properly.
    # if ctx.node.properties['use_external_resource']:
    #     machine = mist_client.machine
    #     ctx.instance.runtime_properties['mist_type'] = 'machine'
    #     ctx.instance.runtime_properties['info'] = machine.info
    #     public_ips = machine.info.get('public_ips', [])
    #     if public_ips:
    #         ctx.instance.runtime_properties['ip'] = public_ips[0]
    #         ctx.instance.runtime_properties['networks'] = public_ips
    #     return

    try:
        name = (
            params.pop('name', '') or  # Get or auto-generate.
            utils.generate_name(stack_name, node_type)
        )
        key = params.pop('key') or ''  # Avoid None.
        size_id = params.pop('size_id')
        image_id = params.pop('image_id')
        location_id = params.pop('location_id')
        job = cloud.create_machine(name, key, image_id, location_id, size_id,
                                   async=True, **params)
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

    # Wait for machine's post-deploy configuration to finish.
    if key and not skip_post_deploy_validation:
        event = utils.wait_for_event(
            job_id=job['job_id'],
            job_kwargs={
                'action': 'post_deploy_finished',
                'machine_id': ctx.instance.runtime_properties['machine_id'],
            }
        )

    # Update the node instance's runtime properties.
    ctx.instance.runtime_properties['machine_name'] = name
    ctx.instance.runtime_properties['job_id'] = job['job_id']

    cloud.update_machines()
    machine_id = ctx.instance.runtime_properties['machine_id']
    machine = cloud.machines(id=machine_id)[0]

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
        connection.MistConnectionClient().machine.start()
    except Exception as exc:
        ctx.logger.error('Failed to start machine. %s', exc)
    if ctx.node.properties.get("monitoring"):
        connection.MistConnectionClient().machine.enable_monitoring()
        ctx.logger.info('Monitoring enabled')


@operation
def stop(**_):
    try:
        connection.MistConnectionClient().machine.stop()
        ctx.logger.info('Machine stopped')
    except Exception as exc:
        ctx.logger.error('Failed to stop machine. %s', exc)


@operation
def delete(**_):
    if not ctx.node.properties['use_external_resource']:
        try:
            connection.MistConnectionClient().machine.destroy()
        except Exception as exc:
            ctx.logger.error('Failed to destroy machine. %s', exc)
    else:
        ctx.logger.info('use_external_resource flag is true, cannot delete.')


@operation
def run_script(**kwargs):
    client = connection.MistConnectionClient().client
    machine = connection.MistConnectionClient().machine
    kwargs['cloud_id'] = machine.cloud.id
    kwargs['machine_id'] = str(machine.id)
    script_params = kwargs.pop("params", "")
    kwargs.pop('ctx', None)
    if kwargs.get("script_id", ''):
        try:
            job_id = client.run_script(**kwargs)
        except Exception as exc:
            raise NonRecoverableError(exc)
    else:
        try:
            response = client.add_and_run_script(machine.cloud.id,
                                                 script_params=script_params,
                                                 fire_and_forget=False,
                                                 **kwargs)
        except Exception as exc:
            raise NonRecoverableError(exc)
