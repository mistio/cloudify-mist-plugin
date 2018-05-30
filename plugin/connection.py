from time import sleep

from mistclient import MistClient
from plugin.utils import get_job_id

from cloudify import ctx
from cloudify.exceptions import NonRecoverableError


class MistConnectionClient(object):

    """Provides functions for getting the Mist Client
    """

    def __init__(self, **kwargs):
        self._client = None
        self._cloud = None
        self._machine = None
        if kwargs.get("properties"):
            self.properties = kwargs.get("properties")
            self.ctx = False
        else:
            self.properties = ctx.node.properties
            self.ctx = True

    @property
    def client(self):
        """Represents the MistConnection Client
        """
        if self._client is None:
            if self.properties['mist_config'].get("mist_uri"):
                mist_uri = self.properties['mist_config']["mist_uri"]
                verify = False
            else:
                mist_uri = "https://mist.io"
                verify = True
            if self.properties['mist_config'].get("mist_token"):
                token = self.properties['mist_config']['mist_token']
                self._client = MistClient(mist_uri=mist_uri,
                                          api_token=token,
                                          verify=verify,
                                          job_id=get_job_id())
            else:
                self._client = MistClient(mist_uri=mist_uri,
                                          email=self.properties['mist_config']['mist_username'],
                                          password=self.properties['mist_config']['mist_password'],
                                          job_id=get_job_id())
        return self._client

    @property
    def cloud(self):
        """Represents the Mist Cloud
        """
        if self._cloud is None:
            if self.properties['parameters'].get("cloud_id"):
                self._cloud = self.client.clouds(
                    id=self.properties['parameters']['cloud_id'])[0]
            elif self.properties['parameters'].get("cloud_name"):
                cloud_search = self.client.clouds(search=self.properties['parameters'][
                                                  'cloud_name'])
                if len(cloud_search) > 1:
                    raise NonRecoverableError("Found more then one cloud with name {0}".format(
                                              self.properties['parameters']['cloud_name']))
                elif len(cloud_search) == 0:
                    raise NonRecoverableError("Did not find cloud with name {0}".format(
                                              self.properties['parameters']['cloud_name']))
                self._cloud = cloud_search[0]
        return self._cloud

    @property
    def machine(self):
        """Represents a Mist Machine
        """
        self.cloud.update_machines()
        if self.properties.get('use_external_resource', ''):
            if self.ctx:
                ctx.logger.info('use external resource enabled')
            if not self.properties["resource_id"]:
                raise NonRecoverableError(
                    "Cannot use external resource without defining resource_id")
            machines = self.cloud.machines(id=str(self.properties["resource_id"]))
            if not len(machines):
                raise NonRecoverableError(
                    "External resource not found")
            if machines[0].info["state"] in ["error", "terminated"]:
                raise NonRecoverableError(
                    "External resource state {0}".format(machines[0].info["state"]))
            return machines[0]

        if self.ctx:
            machine_id = ctx.instance.runtime_properties['machine_id'] or \
                ctx.node.properties['resource_id']
            if machine_id:
                ctx.logger.info('Retrieving machines\' list')
                machines = []
                i = 0
                while not machines and i < 10:
                    machines = self.cloud.machines(id=machine_id)
                    sleep(2)
                    self.cloud.update_machines()
                    i += 1
                if machines:
                    return machines[0]

        machines = self.cloud.machines(search=self.properties['parameters']["name"])
        if len(machines) > 1:
            if self.ctx:
                ctx.logger.info('Found multiple machines with the same name')
            for m in machines:
                if m.name == self.properties['parameters']["name"] and m.info["state"] in ["running", "stopped"]:
                    machines = [m]
                    break
            else:
                raise NonRecoverableError('Could not find machine')

        if self.ctx:
            ctx.instance.runtime_properties['machine_id'] = machines[0].info["id"]
        return machines[0]

    # FIXME
    def other_machine(self, kwargs):
        self.cloud.update_machines()
        if kwargs.get('use_external_resource', ''):
            if not kwargs["resource_id"]:
                raise NonRecoverableError(
                    "Cannot use external resource without defining resource_id")
            machines = self.cloud.machines(id=str(kwargs["resource_id"]))
            if not len(machines):
                raise NonRecoverableError(
                    "External resource not found")
            if machines[0].info["state"] in ["error", "terminated"]:
                raise NonRecoverableError(
                    "External resource state {0}".format(machines[0].info["state"]))
            return machines[0]

        machines = self.cloud.machines(search=kwargs["name"])
        if len(machines) > 1:
            for m in machines:
                if m.info["state"] in ["running", "stopped"]:
                    machines[0] = m
                    break
        return machines[0]
