from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError
from mistclient import MistClient
from time import sleep
import connection
import constants
import keypair
import os
import string , random


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
                '{0} is a required input. Unable to create.'.format(key))
    backend = client.backends(id=ctx.node.properties['backend_id'])
    if not len(backend):
        raise NonRecoverableError(
            '{0} backend was not found.'.format(ctx.node.properties['backend_id']))
    image = ""
    for im in backend[0].images:
        if im[id] == ctx.node.properties['image_id']:
            image = im
            break
    if not image:
        raise NonRecoverableError(
            'image_id {0} not found.'.format(ctx.node.properties['image_id']))
    size = ""
    for si in backend[0].sizes:
        if si[id] == ctx.node.properties['size_id']:
            size = si
            break
    if not size:
        raise NonRecoverableError(
            'size_id {0} not found.'.format(ctx.node.properties['size_id']))
    location = ""
    for lo in backend[0].locations:
        if lo[id] == ctx.node.properties['location_id']:
            location = lo
            break
    if not location:
        raise NonRecoverableError(
            'location_id {0} not found.'.format(ctx.node.properties['location_id']))

    machines = backend[0].machines(search=ctx.node.properties["name"])
    if ctx.node.properties['use_external_resource'] and not len(machines):
        raise NonRecoverableError(
            'machine {0} not found.'.format(ctx.node.properties["name"]))
    if not ctx.node.properties['use_external_resource'] and len(machines):
        raise NonRecoverableError(
            'machine {0} exists.'.format(ctx.node.properties["name"]))
    if ctx.node.properties['use_external_resource'] and len(machines):
        if machines[0].info["state"] == "running":
            pass
        elif machines[0].info["state"] == "stopped":
            machines[0].start()
            delay = 0
            while True:
                sleep(10)
                backend[0].update_machines()
                if backend[0].machines(search=ctx.node.properties["name"])[0].info["state"] == "running":
                    break
                elif delay == 5:
                    raise NonRecoverableError(
                        'machine {0} in stopped state.'.format(ctx.node.properties["name"]))
                delay += 1
        else:
            raise NonRecoverableError(
                'machine {0} error state.'.format(ctx.node.properties["name"]))


@operation
def create(**_):
    mist_client = connection.MistConnectionClient()
    client = mist_client.client
    # backend = client.backends(id=ctx.node.properties['backend_id'])[0]
    backend = mist_client.backend
    if ctx.node.properties['use_external_resource']:
        machine = mist_client.machine
        ctx.instance.runtime_properties['ip'] = machine.info["public_ips"][0]
        ctx.instance.runtime_properties['networks'] = {
            "default": machine.info["public_ips"][0]}
        print machine.info
        ctx.instance.runtime_properties['machine_id'] = machine.info["id"]

        ctx.logger.info('External machine attached to ctx')
        return
    machines = backend.machines(
        search=ctx.node.properties['parameters']["name"])
    if len(machines):
        for m in machines:
            if m.info["state"] in ["running", "stopped"]:
                raise NonRecoverableError(
                    "Machine with name {0} exists".format(ctx.node.properties['parameters']["name"]))

    key = ""
    if ctx.node.properties['parameters'].get("key_name"):
        key = client.keys(search=ctx.node.properties['parameters']["key_name"])
        if len(key):
            key = key[0]
        else:
            # private = client.generate_key()
            # client.add_key(
            #     key_name=ctx.node.properties["key"], private=private)
            # key = client.keys(search=ctx.node.properties["key"])[0]
            # ctx.logger.info('Creating key with key name: {0} .'.format(ctx.node.properties["key"]))

            raise NonRecoverableError("key not found")
    else:
        raise NonRecoverableError("key not found")
        # keys = client.keys()
        # for k in keys:
        #     if k.is_default:
        #         ctx.logger.info('Using default key ')
        #         key = k
        # if not key:
        #     ctx.logger.info(
        #         'No key found. Trying to generate one and add one.')
        #     private = client.generate_key()
        #     client.add_key(
        #         key_name=ctx.node.properties["name"], private=private)
        #     key = client.keys(search=ctx.node.properties["name"])[0]
    print 'Key:', key

    job_id = backend.create_machine(async=True, name=ctx.node.properties['parameters']["name"],
                                    key=key,
                                    image_id=ctx.node.properties[
                                        'parameters']["image_id"],
                                    location_id=ctx.node.properties['parameters'][
        "location_id"],
        size_id=ctx.node.properties['parameters']["size_id"])
    job_id = job_id.json()["job_id"]
    job = client.get_job(job_id)
    timer = 0
    while True:
        if job["summary"]["probe"]["success"]:
            break
        if job["summary"]["create"]["error"] or job["summary"]["probe"]["error"]:
            ctx.logger.error('Error on machine creation ')
            raise NonRecoverableError("Not able to create machine")
        sleep(10)
        job = client.get_job(job_id)
        print job["summary"]
        timer += 1
        if timer >= 60:   # timeout
            raise NonRecoverableError("Timeout.Not able to create machine.")

    machine = mist_client.machine
    ctx.instance.runtime_properties['machine_id'] = machine.info["id"]
    ctx.instance.runtime_properties['ip'] = machine.info["public_ips"][0]
    ctx.instance.runtime_properties['networks'] = {
        "default": machine.info["public_ips"][0]}
    ctx.logger.info('Machine created')


@operation
def start(**_):
    connection.MistConnectionClient().machine.start()
    ctx.logger.info('Machine started')
    if ctx.node.properties.get("monitoring"):
        connection.MistConnectionClient().machine.enable_monitoring()
        ctx.logger.info('Monitoring enabled')


@operation
def stop(**_):
    connection.MistConnectionClient().machine.stop()
    ctx.logger.info('Machine stopped')


@operation
def delete(**_):
    connection.MistConnectionClient().machine.destroy()
    ctx.logger.info('Machine destroyed')


# @operation
# def creation_validation(nova_client, args, **kwargs):
@operation
def run_script(**kwargs):
    print "scriptttttttttt:", kwargs
    client = connection.MistConnectionClient().client
    script = kwargs.get('script', '')
    name = kwargs.get("name", '')
    scripts = client.get_scripts()
    if kwargs.get("script_id", ''):
        script_id = kwargs["script_id"]
        return client.run_script(script_id=script_id, backend_id=ctx.node.properties['parameters']['backend_id'],
                                 machine_id=ctx.instance.runtime_properties[
                                     'machine_id'],
                                 params=kwargs.get("params", ""))
            

    if kwargs.get("exec_type", ''):
        exec_type = kwargs["exec_type"]
    else:
        exec_type = "executable"

    if kwargs.get("location_type", ""):
        location_type = kwargs["location_type"]
    else:
        if (script.startswith('http://github.com') or script.startswith('https://github.com')):
            location_type = 'github'
        elif (script.startswith('http://') or script.startswith('https://')):
            location_type = 'url'
        elif os.path.exists(script):
            if not name:
                name = script.split("/").pop()
            location_type = 'inline'
            with open(script, "r") as scriptfile:
                script = scriptfile.read()
        elif script.startswith("#!"):
            location_type = 'inline'
    # if not name:
    if not name:
        uid=''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        name = ctx.node.properties["parameters"]["name"]+uid

    for s in scripts:
        if s['name'] == name:
            raise NonRecoverableError("Script with name {0} exists. Rename the script \
                                        or use external resource.".format(name))
    response = client.add_script(
        name=name, script=script, location_type=location_type, exec_type=exec_type)
    print response
    script_id = response['script_id']
    if kwargs.get("params", ""):
        params=kwargs["params"]
        return client.run_script(script_id=script_id, backend_id=ctx.node.properties['parameters']['backend_id'],
                                 machine_id=ctx.instance.runtime_properties['machine_id'],params=params)
    else:
        return client.run_script(script_id=script_id, backend_id=ctx.node.properties['parameters']['backend_id'],
                                 machine_id=ctx.instance.runtime_properties['machine_id'])
