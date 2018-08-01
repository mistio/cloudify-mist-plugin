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

STORAGE = (
    "/tmp/templates/kubernetes-blueprint/local-storage/local/node-instances"
)

CLOUD_INIT_PROVIDERS = [
    "libvirt"
]
