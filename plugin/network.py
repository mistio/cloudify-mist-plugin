from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError
import connection



@operation
def create(**_):
    params = ctx.node.properties['parameters']
    cloud = connection.MistConnectionClient().cloud
    del params["cloud_id"]
    try:
        network = cloud.create_network(**params)

        ctx.instance.runtime_properties["info"] = network
    except Exception as exc:
        raise Exception(exc)
    # connection.MistConnectionClient().machine.destroy()
    # ctx.logger.info('Machine destroyed')



@operation
def delete(**_):

    try:
        network_id = ctx.instance.runtime_properties["info"]["id"]
        connection.MistConnectionClient().cloud.delete_network(network_id)
    except Exception as exc:
        raise Exception(exc)
    # connection.MistConnectionClient().machine.destroy()
    # ctx.logger.info('Machine destroyed')

@operation
def associate_network(**kwargs):
    ip = kwargs.get("ip")
    assign = kwargs.get("assign")
    machine_id = ctx.target.instance.runtime_properties["machine_id"]
    cloud_id = ctx.target.node.properties["cloud_id"]