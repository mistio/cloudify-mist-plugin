from cloudify import ctx
from cloudify.decorators import operation


@operation
def create(**kwargs):
    print 'create', kwargs
    ctx.instance.runtime_properties['some_property'] = 'new_test_input'


@operation
def start(**kwargs):
    print 'start', kwargs
