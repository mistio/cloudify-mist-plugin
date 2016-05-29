from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from time import sleep
import connection
import os
import uuid
import pkg_resources
import requests


resource_package = __name__  ## Could be any module/package name.
resource_path = os.path.join('scripts', 'worker.sh')
install_worker_script = pkg_resources.resource_string(resource_package, resource_path)
resource_path = os.path.join('scripts', 'master.sh')
install_master_script = pkg_resources.resource_string(resource_package, resource_path)
resource_path = os.path.join('scripts', 'coreos_master.sh')
install_coreos_master_script = pkg_resources.resource_string(resource_package, resource_path)
resource_path = os.path.join('scripts', 'coreos_worker.sh')
install_coreos_worker_script = pkg_resources.resource_string(resource_package, resource_path)

from cloudify.decorators import workflow

from cloudify.workflows import ctx as workctx

@workflow
def scale_cluster_up(**kwargs):

    master = workctx.get_node("master")
    mist_client = connection.MistConnectionClient(properties=master.properties)
    client = mist_client.client
    cloud = mist_client.cloud
    master_machine = mist_client.machine
    master_ip = master_machine.info["private_ips"][0]

    if kwargs['use_external_resource']:
        machine = mist_client.other_machine(kwargs)
    machine_name = kwargs["name"]
    machines = cloud.machines(search=machine_name)
    if len(machines):
        for m in machines:
            if m.info["state"] in ["running", "stopped"]:
                raise NonRecoverableError(
                    "Machine with name {0} exists".format(machine_name))

    key = ""
    if kwargs.get("key_name"):
        key = client.keys(search=kwargs["key_name"])
        if len(key):
            key = key[0]
        else:
            raise NonRecoverableError("key not found")
    else:
        raise NonRecoverableError("key not found")
    # print 'Key:', key
    if kwargs.get("networks"):
        networks = kwargs["networks"]
    else:
        networks = []
    quantity = kwargs.get("delta")
    job_id = cloud.create_machine(async=True, name=machine_name,
                                  key=key, image_id=kwargs["image_id"],
                                  location_id=kwargs["location_id"],
                                  size_id=kwargs["size_id"], quantity=quantity,
                                  networks=networks)
    job_id = job_id.json()["job_id"]
    job = client.get_job(job_id)
    timer = 0
    while True:
        if job["summary"]["probe"]["success"]:
            break
        if job["summary"]["create"]["error"] or job["summary"]["probe"]["error"]:
            workctx.logger.error('Error on machine creation:{0}'.format(job))
            raise NonRecoverableError("Not able to create machine")
        sleep(10)
        job = client.get_job(job_id)
        timer += 1
        if timer >= 360:   # timeout 1hour
            raise NonRecoverableError("Timeout.Not able to create machine.")

    kub_type = "worker"

    if not kwargs["coreos"]:
        script = """#!/bin/sh
        command_exists() {
        command -v "$@" > /dev/null 2>&1
        }
        if command_exists curl; then
        curl -sSL https://get.docker.com/ | sh
        elif command_exists wget; then
        wget -qO- https://get.docker.com/ | sh
        fi
        """
        response = client.add_script(
            name="install_docker" + kub_type + uuid.uuid1().hex, script=script,
            location_type="inline", exec_type="executable",
        )
        script_id = response['script_id']
        machine_id = kwargs['machine_id']
        cloud_id = kwargs['cloud_id']
        job_id = client.run_script(script_id=script_id, cloud_id=cloud_id,
                                   machine_id=machine_id,
                                   script_params="",
                                   su=False)
        workctx.logger.info("Docker installation started")
        job_id = job_id["job_id"]
        job = client.get_job(job_id)
        while True:
            if job["error"]:
                raise NonRecoverableError("Not able to install docker")
            if job["finished_at"]:
                break
            sleep(10)
            job = client.get_job(job_id)
        workctx.logger.info(job["logs"][2]['stdout'])
        workctx.logger.info(job["logs"][2]['extra_output'])
        workctx.logger.info("Docker installation script succeeded")
    if kwargs["coreos"]:
        install_script = install_coreos_worker_script
    else:
        install_script = install_worker_script
    response = client.add_script(
        name="install_kubernetes_worker" + uuid.uuid1().hex,
        script=install_script,
        location_type="inline", exec_type="executable",
    )
    for m in xrange(quantity):
        kwargs["name"] = machine_name + "-" + str(m + 1)
        kwargs["machine_id"] = ""
        machine = mist_client.other_machine(kwargs)
        kwargs["machine_id"] = machine.info["id"]
        workctx.logger.info('Machine created')

        script_id = response['script_id']
        machine_id = kwargs['machine_id']
        cloud_id = kwargs['cloud_id']
        script_params = "-m '{0}'".format(master_ip)
        job_id = client.run_script(script_id=script_id, cloud_id=cloud_id,
                                   machine_id=machine_id,
                                   script_params=script_params,
                                   su=True)
        workctx.logger.info("Kubernetes worker installation started")
        job_id = job_id["job_id"]
        job = client.get_job(job_id)
        while True:
            if job["error"]:
                raise NonRecoverableError("Not able to install kubernetes worker")
            if job["finished_at"]:
                break
            sleep(10)
            job = client.get_job(job_id)
        workctx.logger.info(job["logs"][2]['stdout'])
        workctx.logger.info(job["logs"][2]['extra_output'])
        workctx.logger.info("Kubernetes worker {0} installation script succeeded".format(kwargs["name"]))
    workctx.logger.info("Upscaling kubernetes cluster succeeded")


@workflow
def scale_cluster_down(**kwargs):
    master = workctx.get_node("master")
    mist_client = connection.MistConnectionClient(properties=master.properties)
    client = mist_client.client
    cloud = mist_client.cloud
    master_machine = mist_client.machine
    master_ip = master_machine.info["public_ips"][0]

    worker_name = kwargs.get("name")
    machines = cloud.machines(search=worker_name)
    delta = kwargs.get("delta")
    counter = 0
    for m in machines:
        if not m.info["state"] in ("stopped", "running"):
            continue
        counter += 1
        worker_priv_ip = m.info["private_ips"][0]
        m.destroy()
        requests.delete("http://%s:8080/api/v1/nodes/%s" % (master_ip, worker_priv_ip))
        if counter == delta:
            break
    workctx.logger.info("Downscaling kubernetes cluster succeeded")



@operation
def install_kubernetes(**kwargs):
    client = connection.MistConnectionClient().client
    machine = connection.MistConnectionClient().machine
    if kwargs.get("master"):
        ctx.instance.runtime_properties["master_ip"] = machine.info["private_ips"][0]
        kub_type = "master"
        if ctx.node.properties["coreos"]:
            install_script = install_coreos_master_script
        else:
            install_script = install_master_script
    else:
        ctx.instance.runtime_properties["master_ip"] = ctx.instance.relationships[0]._target.instance.runtime_properties["master_ip"]
        if ctx.node.properties["coreos"]:
            install_script = install_coreos_worker_script
        else:
            install_script = install_worker_script
        kub_type = "worker"

    if ctx.node.properties["configured"]:
        return
    if not ctx.node.properties["coreos"]:
        script = """#!/bin/sh
        command_exists() {
        command -v "$@" > /dev/null 2>&1
        }
        if command_exists curl; then
        curl -sSL https://get.docker.com/ | sh
        elif command_exists wget; then
        wget -qO- https://get.docker.com/ | sh
        fi
        """
        response = client.add_script(
            name="install_docker" + kub_type + uuid.uuid1().hex, script=script,
            location_type="inline", exec_type="executable",
        )
        script_id = response['script_id']
        machine_id = ctx.instance.runtime_properties['machine_id']
        cloud_id = ctx.node.properties['parameters']['cloud_id']
        job_id = client.run_script(script_id=script_id, cloud_id=cloud_id,
                                   machine_id=machine_id,
                                   script_params="",
                                   su=False)
        ctx.logger.info("Docker installation started")
        job_id = job_id["job_id"]
        job = client.get_job(job_id)
        while True:
            if job["error"]:
                raise NonRecoverableError("Not able to install docker")
            if job["finished_at"]:
                break
            sleep(10)
            job = client.get_job(job_id)
        ctx.logger.info(job["logs"][2]['stdout'])
        ctx.logger.info(job["logs"][2]['extra_output'])
        ctx.logger.info("Docker installation script succeeded")
    response = client.add_script(
        name="install_kubernetes_" + kub_type + uuid.uuid1().hex,
        script=install_script,
        location_type="inline", exec_type="executable",
    )
    script_id = response['script_id']
    machine_id = ctx.instance.runtime_properties['machine_id']
    cloud_id = ctx.node.properties['parameters']['cloud_id']
    if kub_type == "master":
        script_params = ""
    else:
        script_params = "-m '{0}'".format(ctx.instance.runtime_properties["master_ip"])
    job_id = client.run_script(script_id=script_id, cloud_id=cloud_id,
                               machine_id=machine_id,
                               script_params=script_params,
                               su=True)
    ctx.logger.info("Kubernetes {0} installation started".format(kub_type))
    job_id = job_id["job_id"]
    job = client.get_job(job_id)
    while True:
        if job["error"]:
            raise NonRecoverableError("Not able to install kubernetes {0}".format(kub_type))
        if job["finished_at"]:
            break
        sleep(10)
        job = client.get_job(job_id)
    ctx.logger.info(job["logs"][2]['stdout'])
    ctx.logger.info(job["logs"][2]['extra_output'])
    ctx.logger.info("Kubernetes {0} installation script succeeded".format(kub_type))

