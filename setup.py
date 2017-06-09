from setuptools import setup


setup(
    name='cloudify-mist-plugin',

    version='0.0.10',
    author='mist.io',
    author_email='support@mist.io',
    description='A Cloudify Plugin that provisions resources across IaaS '
                'Cloud Providers through Mist.io',

    packages=['plugin'],

    license='LICENSE',
    zip_safe=False,
    install_requires=[
        # Necessary dependency for developing plugins, do not remove!
        'cloudify-plugins-common==3.3',
    ],
    dependency_links=[
        'https://github.com/mistio/mist.client/archive/master.zip',
    ],
    test_requires=[
        'cloudify-dsl-parser==3.3',
        'nose',
    ]
)
