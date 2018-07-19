from cloudify import ctx
from cloudify.exceptions import NonRecoverableError

from mistclient import MistClient

from plugin.utils import get_job_id


class MistConnectionClient(object):

    def __init__(self, *args, **kwargs):
        """Return a wrapper instance around mistclient.MistClient

        This object is just a helper around mistclient.MistClient that helps
        communicate with the mist.io API.

        The client is bound to a single job_id to group all of the workflow's
        logs into a single story.

        The client requires that the mist_config property is configured per
        node template of the respective blueprint so that the client may be
        authenticated to the mist.io API and instantiated.

        """
        self._client = None

        # FIXME Undo this when the scale-down workflow of the kubernetes
        # blueprint is re-factored.
        self.node_properties = kwargs.get('properties') or ctx.node.properties

        # Connection parameters.
        self._uri = self._config.get('mist_uri')
        self._token = self._config.get('mist_token')
        self._verify = self._uri.startswith('https')

        # The job_id associated with the current workflow. Required to group
        # log entries into a single story representing all of the workflow's
        # actions.
        self.job_id = get_job_id()

    @property
    def client(self):
        """Return a cached MistClient connection object"""
        if self._client is None:
            self._client = self._get_connection()
        return self._client

    @property
    def _config(self):
        """Return the settings required to authenticate to the mist.io API"""
        _config = self.node_properties.get('mist_config', {})
        if not _config:
            raise NonRecoverableError('Authentication: mist_config missing!')
        if not _config.get('mist_token'):
            raise NonRecoverableError('Authentication: mist_token not set!')
        return _config

    def _get_connection(self):
        """Return an authenticated MistClient connection instance"""
        return MistClient(mist_uri=self._uri, verify=self._verify,
                          api_token=self._token, job_id=self.job_id)

    def get_cloud(self, cloud_id):
        """Return a MistClient Cloud object based on its cloud_id"""
        clouds = self.client.clouds(id=str(cloud_id))
        if len(clouds) == 0:
            raise NonRecoverableError('Cloud %s not found' % cloud_id)
        if len(clouds) >= 2:
            raise NonRecoverableError('Got multiple clouds: %s' % clouds)
        return clouds[0]

    def get_machine(self, cloud_id, machine_id):
        """Return a MistClient Machine object"""
        cloud = self.get_cloud(cloud_id)
        cloud.update_machines()
        machines = cloud.machines(id=str(machine_id))
        if len(machines) == 0:
            raise NonRecoverableError('Machine %s not found' % machine_id)
        if len(machines) >= 2:
            raise NonRecoverableError('Got multiple machines: %s' % machines)
        return machines[0]
