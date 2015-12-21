from cloudify import ctx
from mistclient import MistClient
from cloudify.exceptions import NonRecoverableError


class MistConnectionClient(object):

    """Provides functions for getting the Mist Client
    """

    def __init__(self):
        self._client = None
        self._cloud = None
        self._machine = None

    @property
    def client(self):
        """Represents the MistConnection Client
        """
        if self._client is None:
            if ctx.node.properties['mist_config'].get("mist_uri"):
                mist_uri = ctx.node.properties['mist_config']["mist_uri"]
            else:
                mist_uri = "https://mist.io"
            if ctx.node.properties['mist_config'].get("api_token"):
                token = ctx.node.properties['mist_config']['api_token']
                self._client = MistClient(mist_uri= mist_uri,
                                          api_token= token)
            else:
                self._client = MistClient(mist_uri= mist_uri,
                                          email=ctx.node.properties['mist_config']['username'],
                                          password=ctx.node.properties['mist_config']['password'])
        return self._client

    @property
    def cloud(self):
        """Represents the Mist Cloud
        """
        if self._cloud is None:
            if ctx.node.properties['parameters'].get("cloud_id"):
                self._cloud = self.client.clouds(
                    id=ctx.node.properties['parameters']['cloud_id'])[0]
            elif ctx.node.properties['parameters'].get("cloud_name"):
                cloud_search = self.client.clouds(search=ctx.node.properties['parameters'][
                                                       'cloud_name'])
                if len(cloud_search) > 1:
                    raise NonRecoverableError("Found more then one cloud with name {0}".format(
                                                ctx.node.properties['parameters']['cloud_name']))
                elif len(cloud_search) == 0:
                    raise NonRecoverableError("Did not find cloud with name {0}".format(
                                                ctx.node.properties['parameters']['cloud_name']))
                self._cloud = cloud_search[0]
        return self._cloud

    @property
    def machine(self):
        """Represents a Mist Machine
        """
        self.cloud.update_machines()
        if ctx.node.properties.get('use_external_resource',''):
            ctx.logger.info('use external resource enabled')
            if not ctx.node.properties["resource_id"]:
                raise NonRecoverableError(
                    "Cannot use external resource without defining resource_id")
            machines = self.cloud.machines(id=ctx.node.properties["resource_id"])
            if not len(machines):
                raise NonRecoverableError(
                    "External resource not found")
            if machines[0].info["state"] in ["error","terminated"]:
                raise NonRecoverableError(
                    "External resource state {0}".format(machines[0].info["state"]))
            return machines[0]


        if ctx.instance.runtime_properties.get('machine_id'):
            return self.cloud.machines(id=ctx.instance.runtime_properties['machine_id'])[0]
        machines = self.cloud.machines(search=ctx.node.properties['parameters']["name"])
        if len(machines) > 1:
            ctx.logger.info('Found multiple machines with the same name')
            for m in machines:
                if m.info["state"] in ["running","stopped"]:
                    machines[0] = m
                    break
        ctx.instance.runtime_properties['machine_id']=machines[0].info["id"]
        return machines[0]
