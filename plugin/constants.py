INSTANCE_REQUIRED_PROPERTIES = [
    'mist_username',
    'mist_password',
    'name',
    'key',
    'cloud_id',
    'image_id',
    'size_id',
    'location_id'
]

STORAGE = 'local-storage/local/node-instances/%s_[A-Za-z0-9]*'
STORAGE2 = '/tmp/templates/mistio-kubernetes-blueprint-[A-Za-z0-9]*/local-storage/local/node-instances'

CREATE_TIMEOUT = 60 * 10
SCRIPT_TIMEOUT = 60 * 30

CLOUD_INIT_PROVIDERS = [
    "libvirt"
]
