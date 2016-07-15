from setuptools import setup


setup(
    name='cloudify-mist-plugin',
    version='0.0.10',
    author='mist',
    author_email='info@mist.io',
    description='Cloudify plugin for Mist infrastructure.',
    packages=['plugin'],
    license='LICENSE',
    zip_safe=False,
    install_requires=[
        # Necessary dependency for developing plugins, do not remove!
        'cloudify-plugins-common==3.4',
    ],
    dependency_links=[
        'https://github.com/mistio/mist.client/archive/master.zip',
    ],
    test_requires=[
        'cloudify-dsl-parser==3.4',
        'nose',
    ]
)
