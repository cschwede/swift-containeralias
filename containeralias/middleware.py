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

from swift.common.swob import wsgify, HTTPBadRequest
from swift.common.utils import split_path
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


    @wsgify
    def __call__(self, request):
        try:
            (version, account, container, objname) = split_path(
                                  request.path_info, 1, 4, True)
        except ValueError:
            return self.app(environ, start_response)

        if container and not objname:
            if request.method in ('DELETE', 'HEAD'):
                return self.app

            if request.method == 'POST':
                # Deny setting if there are any objects in base container
                # Otherwise these objects won't be visible
                if request.headers.get('X-Container-Meta-Storage-Path'):
                    container_info = get_container_info(request.environ, self.app)
                    objects = container_info.get('object_count')
                    if objects and int(objects) > 0:
                        return HTTPBadRequest()

                # ACL set
                groups = (request.remote_user or '').split(',')
                account_name = groups[0].split(':')[0]
                read_acl = request.environ.get('HTTP_X_CONTAINER_READ', '')
                for target_account in read_acl.split(','):
                    target_account = target_account.split(':')[0]
                    target_storage_path = self._get_storage_path(request, 
                                                                 target_account)
                   
                    if not target_storage_path or account_name == target_account:
                        continue
                        
                    container_path = "/%s/%s/%s" % (version, account, container)
                    headers = {'X-Container-Meta-Storage-Path': container_path}
                    request_path = "%s/%s%s_%s" % (target_storage_path,
                                                   self.prefix,
                                                   account_name,
                                                    container)

                    req = make_pre_authed_request(request.environ, 'PUT',
                                                  request_path, headers=headers)
    
                    req.get_response(self.app)

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
