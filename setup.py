from setuptools import setup


setup(
    name='cloudify-mist-plugin',
    version='0.0.9',
    author='mist',
    author_email='info@mist.io',
    description='Cloudify plugin for Mist infrastructure.',
    packages=['plugin'],
    license='LICENSE',
    zip_safe=False,
    install_requires=[
        # Necessary dependency for developing plugins, do not remove!
        'cloudify-plugins-common>=3.3a5',
        'mist',
    ],
    test_requires=[
        'cloudify-dsl-parser>=3.3a5',
        'nose',
    ]
)
