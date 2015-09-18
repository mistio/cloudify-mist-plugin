from cloudify import ctx
from mistclient import MistClient
from cloudify.exceptions import NonRecoverableError


class MistConnectionClient(object):

    """Provides functions for getting the Mist Client
    """

    def __init__(self):
        self._client = None
        self._backend = None
        self._machine = None

    @property
    def client(self):
        """Represents the MistConnection Client
        """
        if self._client is None:
            self._client = MistClient(email=ctx.node.properties['username'],
                                      password=ctx.node.properties['password'])
        return self._client

    @property
    def backend(self):
        """Represents the Mist Backend
        """
        if self._backend is None:
            self._backend = self.client.backends(
                id=ctx.node.properties['backend_id'])[0]
        return self._backend

    @property
    def machine(self):
        """Represents a Mist Machine
        """
        self.backend.update_machines()

        if ctx.node.properties['use_external_resource']:
            ctx.logger.info('use external resource enabled')
            if not ctx.node.properties["resource_id"]:
                raise NonRecoverableError(
                    "Cannot use external resource without defining resource_id")
            machines = self.backend.machines(id=ctx.node.properties["resource_id"])
            if not len(machines):
                raise NonRecoverableError(
                    "External resource not found")
            if machines[0].info["state"] in ["error","terminated"]:
            	raise NonRecoverableError(
                    "External resource state {0}".format(machines[0].info["state"]))    
            return machines[0]
        if ctx.instance.runtime_properties.get('machine_id'):
            return self.backend.machines(id=ctx.instance.runtime_properties['machine_id'])[0]
        machines = self.backend.machines(search=ctx.node.properties["name"])
        if len(machines) > 1:
            ctx.logger.info('Found multiple machines with the same name')
            for m in machines:
                if m.info["state"] in ["running","stopped"]:
                    machines[0] = m
                    break
        ctx.logger.info(machines[0].info)
        ctx.instance.runtime_properties['machine_id']=machines[0].info["id"]
        return machines[0]
