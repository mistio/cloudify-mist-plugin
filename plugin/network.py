from plugin import connection

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError


# TODO Improve, validate inputs, test!


@operation
def create(**_):
    params = ctx.node.properties['parameters']
    conn = connection.MistConnectionClient()
    cloud = conn.get_cloud(params.pop('cloud_id'))
    try:
        network = cloud.create_network(**params)

        ctx.instance.runtime_properties["info"] = network
    except Exception as exc:
        raise Exception(exc)


@operation
def delete(**_):
    try:
        network_id = ctx.instance.runtime_properties["info"]["id"]
        conn = connection.MistConnectionClient()
        cloud = conn.get_cloud(ctx.node.properties["parameters"]["cloud_id"])
        cloud.delete_network(network_id)
    except Exception as exc:
        raise Exception(exc)


# TODO
# @operation
# def associate_network(**kwargs):
#     ip = kwargs.get("ip")
#     assign = kwargs.get("assign")
#     machine_id = ctx.target.instance.runtime_properties["machine_id"]
#     cloud_id = ctx.target.node.properties["cloud_id"]
