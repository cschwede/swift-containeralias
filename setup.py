# -*- encoding: utf-8 -*-
__author__ = "Christian Schwede <info@cschwede.de>, Christopher Bartz <bartz@dkrz.de>"
name = 'containeralias'
entry_point = '%s.middleware:filter_factory' % (name)
version = '0.2'

from setuptools import setup, find_packages

setup(
    name=name,
    version=version,
    description='Openstack Swift container alias',
    license='Apache License (2.0)',
    author='Christian Schwede, Christopher Bartz',
    author_email='info@cschwede.de, bartz@dkrz.de',
    url='https://github.com/cschwede/swift-%s' % (name),
    packages=find_packages(),
    test_suite='nose.collector',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.6',
        'Environment :: No Input/Output (Daemon)'],
    install_requires=['swift', 'python-keystoneclient'],
    entry_points={
        'paste.filter_factory': ['%s=%s' % (name, entry_point)]
    },
)
