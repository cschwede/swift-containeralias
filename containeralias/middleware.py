# Copyright (c) 2013 Christian Schwede <info@cschwede.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
``containeralias`` is a middleware which redirects requests to a different
container given by the ``x-container-meta-storage-path`` container metadata
entry. The target container can also reside within another account.

Additionally this middleware creates an alias container for every
cross-account ACL set.

The ``containeralias`` middleware should be added to the pipeline in your
``/etc/swift/proxy-server.conf`` file.
For example::

[pipeline:main]
pipeline = catch_errors cache tempauth containeralias proxy-server

[filter:containeralias]
use = egg:containeralias#containeralias
auth_method = swauth
#prefix = SHARED_
#reseller_prefix = AUTH 

"""

import json
from urlparse import urlparse

try:
    from keystoneclient.v2_0 import client as keystone
except ImportError:
    keystone = None
from swift.common.swob import wsgify, HTTPBadRequest
from swift.common.utils import get_logger, split_path
from swift.proxy.controllers.base import get_container_info
from swift.common.wsgi import make_pre_authed_request


class ContainerAliasMiddleware(object):
    """ Containeralias middleware

    See above for a full description.

    """

    def __init__(self, app, conf, *args, **kwargs):
        self.app = app
        self.prefix = conf.get('prefix', 'SHARED_')
        self.auth_method = conf.get('auth_method', 'tempauth')
        self.reseller_prefix = conf.get('reseller_prefix', 'AUTH')
        self.logger = get_logger(conf)
        if self.auth_method == 'keystone':
            if keystone:
                self.kclient = keystone.Client(
                    username=conf.get('keystone_admin_user', 'admin'),
                    password=conf.get('keystone_admin_password'),
                    tenant_name=conf.get('keystone_admin_tenant', 'admin'),
                    auth_url=conf.get('keystone_admin_uri'))
            else:
                self.logger.error(
                    "Keystone authentication requested, "
                    "but python-keystoneclient module not found")

    def _swauth_lookup(self, request, account):
        storage_url = None
        request_path = '/v1/%s_.auth/%s/.services' % (self.reseller_prefix,
                                                      account)
        request = make_pre_authed_request(request.environ, 'GET', request_path)

        resp = request.get_response(self.app)
        try:
            body = json.loads(resp.body)
        except ValueError:
            return None

        storage_url = body.get('storage', {}).get('cluster_name')
        if storage_url:
            return urlparse(storage_url).path
        return None

    def _keystone_lookup(self, account):
        tenants = self.kclient.tenants.list()

        for t in tenants:
            if t.name == account:
                return '/v1/%s_%s' % (self.reseller_prefix, t.id)

        return None

    def _get_storage_path(self, request, account):
        storage_path = None
        if self.auth_method == 'tempauth':
            storage_path = "/v1/%s_%s" % (self.reseller_prefix, account)

        if self.auth_method == 'keystone':
            storage_path = self._keystone_lookup(account)

        if self.auth_method == 'swauth':
            storage_path = self._swauth_lookup(request, account)

        return storage_path

    def _create_target_containers(self, request, container_path, account_name, container, target_accounts):
        for target_account in target_accounts:
            target_storage_path = self._get_storage_path(request, target_account)

            if not target_storage_path or account_name == target_account:
                continue

            headers = {'X-Container-Meta-Storage-Path': container_path}
            request_path = "%s/%s%s_%s" % (target_storage_path, self.prefix,
                                           account_name, container)

            req = make_pre_authed_request(request.environ, 'PUT',
                                          request_path, headers=headers)

            req.get_response(self.app)

    def _delete_target_containers(self, request, account_name, container, target_accounts):
        for target_account in target_accounts:
            target_storage_path = self._get_storage_path(request, target_account)

            if not target_storage_path or account_name == target_account:
                continue

            request_path = "%s/%s%s_%s" % (target_storage_path, self.prefix,
                                           account_name, container)

            req = make_pre_authed_request(request.environ, 'DELETE',
                                          request_path)
            req.get_response(self.app)

    @wsgify
    def __call__(self, request):
        try:
            (version, account, container, objname) = split_path(request.path_info, 1, 4, True)
        except ValueError:
            return self.app

        if container and not objname:
            if request.method == 'HEAD':
                return self.app

            try:
                groups = (request.remote_user or '').split(',')
                account_name = groups[0].split(':')[0]
            except AttributeError:
                # Then we are using Keystone.
                account_name = request.remote_user[1]

            if request.method == 'DELETE':
                container_info = get_container_info(request.environ, self.app)
                read_acl = container_info.get('read_acl') or ''

                # Delete target containers.
                target_accounts = set()
                for u in read_acl.split(','):
                    target_accounts.add(u.split(':')[0])

                self._delete_target_containers(request, account_name, container, target_accounts)

                return self.app

            if request.method == 'POST':
                container_info = get_container_info(request.environ, self.app)
                # Deny setting if there are any objects in base container
                # Otherwise these objects won't be visible
                if request.headers.get('X-Container-Meta-Storage-Path'):

                    objects = container_info.get('object_count')
                    if objects and int(objects) > 0:
                        return HTTPBadRequest()

                old_read_acl = container_info.get('read_acl') or ''
                new_read_acl = request.environ.get('HTTP_X_CONTAINER_READ', '')

                old_accounts = set([t.split(':')[0] for t in old_read_acl.split(',')])
                new_accounts = set([t.split(':')[0] for t in new_read_acl.split(',')])
 
                # Delete target containers, if no read_acl does anymore exist.
                self._delete_target_containers(request, account_name, container,
                                               old_accounts - new_accounts)

                # Create new target containers.
                container_path = "/%s/%s/%s" % (version, account, container)
                self._create_target_containers(request, container_path,
                                               account_name, container, 
                                               new_accounts - old_accounts)

        if container:
            container_info = get_container_info(request.environ, self.app)
            meta = container_info.get('meta', {})
            storage_path = meta.get('storage-path')
            if storage_path:
                if objname:
                    storage_path += '/' + objname
                request.environ['PATH_INFO'] = storage_path
                request.environ['RAW_PATH_INFO'] = storage_path
        return self.app


def filter_factory(global_conf, **local_conf):
    """Returns a WSGI filter app for use with paste.deploy."""
    conf = global_conf.copy()
    conf.update(local_conf)

    def containeralias_filter(app):
        return ContainerAliasMiddleware(app, conf)
    return containeralias_filter
