import os
import time
import string
import random

from plugin import utils
from plugin import keypair
from plugin import constants
from plugin import connection

from mistclient import MistClient

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError


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


@operation
def create(**kwargs):
    stack_name = utils.get_stack_name()
    node_type = kwargs.get('node_type', 'instance')

    mist_client = connection.MistConnectionClient()
    try:
        client = mist_client.client
    except:
        raise NonRecoverableError('User authentication failed')

    params = ctx.node.properties['parameters']
    cloud_id = params.get('cloud_id')
    cloud = client.clouds(id=cloud_id)[0]

    if ctx.node.properties['use_external_resource']:
        machine = mist_client.machine
        ctx.instance.runtime_properties['mist_type'] = 'machine'
        ctx.instance.runtime_properties['info'] = machine.info
        public_ips = machine.info.get('public_ips', [])
        if public_ips:
            ctx.instance.runtime_properties['ip'] = public_ips[0]
            ctx.instance.runtime_properties['networks'] = public_ips
        return

    try:
        params.pop('cloud_id')
        name = params.pop('name', '') or utils.generate_name(stack_name,
                                                             node_type)
        key = params.pop('key')
        image_id = params.pop('image_id')
        location_id = params.pop('location_id')
        size_id = params.pop('size_id')
        if cloud.provider in constants.CLOUD_INIT_PROVIDERS:
            cloud_init = kwargs.get('cloud_init', '')
            env_vars = kwargs.get('env_vars', '')
            params.update({'env_vars': env_vars, 'cloud_init': cloud_init})
        job = cloud.create_machine(name, key, image_id, location_id, size_id,
                                   async=True, fire_and_forget=False, **params)
        for log in job['logs']:
            if log['action'] == 'machine_creation_finished' and log[
                                                     'machine_name'] == name:
                ctx.instance.runtime_properties[
                    'machine_id'] = log['machine_id']
                break
    except Exception as exc:
        raise NonRecoverableError(exc)

    machine_id = ctx.instance.runtime_properties[
        'machine_id'] or ctx.node.properties['resource_id']
    cloud.update_machines()
    machine = cloud.machines(id=machine_id)[0]
    ctx.instance.runtime_properties['cloud_id'] = cloud_id
    ctx.instance.runtime_properties['mist_type'] = 'machine'
    ctx.instance.runtime_properties['info'] = machine.info
    public_ips = machine.info.get('public_ips', [])
    # Filter out IPv6 addresses
    public_ips = filter(lambda ip: ':' not in ip, public_ips)
    if public_ips:
        ctx.instance.runtime_properties['ip'] = public_ips[0]
        ctx.instance.runtime_properties['networks'] = public_ips


@operation
def start(**_):
    try:
        connection.MistConnectionClient().machine.start()
    except Exception as exc:
        ctx.logger.error("Failed to start machine. Already running?")
    if ctx.node.properties.get("monitoring"):
        connection.MistConnectionClient().machine.enable_monitoring()
        ctx.logger.info('Monitoring enabled')


@operation
def stop(**_):
    try:
        connection.MistConnectionClient().machine.stop()
        ctx.logger.info('Machine stopped')
    except Exception as exc:
        ctx.logger.error('Failed to stop machine. Is \'stop\' supported?')


@operation
def delete(**_):
    if not ctx.node.properties['use_external_resource']:
        try:
            connection.MistConnectionClient().machine.destroy()
        except Exception as exc:
            raise Exception(exc)
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
