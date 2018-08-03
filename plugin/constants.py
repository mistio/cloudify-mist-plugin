INSTANCE_REQUIRED_PROPERTIES = (
    'cloud_id',
    'key_id',
    'size_id',
    'image_id',
    'location_id',
    'networks',
)

STORAGE = (
    "/tmp/templates/kubernetes-blueprint/local-storage/local/node-instances"
)

CLOUD_INIT_PROVIDERS = [
    "libvirt"
]
