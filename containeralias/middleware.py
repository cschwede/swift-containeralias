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

The ``containeralias`` middleware should be added to the pipeline in your
``/etc/swift/proxy-server.conf`` file.
For example::

[pipeline:main]
pipeline = catch_errors cache tempauth containeralias proxy-server

[filter:containeralias]
use = egg:containeralias#containeralias

"""


from swift.common.swob import wsgify, HTTPBadRequest
from swift.common.utils import split_path
from swift.proxy.controllers.base import get_container_info


class ContainerAliasMiddleware(object):
    """ Containeralias middleware

    See above for a full description.

    """

    def __init__(self, app, conf, *args, **kwargs):
        self.app = app

    @wsgify
    def __call__(self, request):
        try:
            (version, account, container, objname) = split_path(
                                  request.path_info, 1, 4, True)
        except ValueError:
            return self.app(environ, start_response)

        if container and not objname:
            if request.method == 'DELETE':
                return self.app

            if request.method == 'POST':
                # Deny setting if there are any objects in base container
                # Otherwise these objects won't be visible
                new_container_alias = request.headers.get(
                    'X-Container-Meta-Storage-Path')

                if new_container_alias:
                    try:
                        (acc, cont) = split_path(new_container_alias, 2, 2, False)
                    except ValueError:
                        return HTTPBadRequest()

                    container_info = get_container_info(
                        request.environ, self.app)
                    objects = container_info.get('object_count')
                    if objects and int(objects) > 0:
                        return HTTPBadRequest()

                    # make sure there is no alias on the target container
                    # otherwise loops could be created
                    old_path_info = request.environ['PATH_INFO']
                    request.environ['PATH_INFO'] = '/%s%s' % (
                        version, new_container_alias)
                    container_info = get_container_info(
                        request.environ, self.app)
                    container_alias = container_info.get(
                        'meta', {}).get('storage_path')
                    request.environ['PATH_INFO'] = old_path_info
                    if container_alias:
                        return HTTPBadRequest()

        if container:
            container_info = get_container_info(request.environ, self.app)
            storage_path = container_info.get('meta', {}).get('storage_path')
            if storage_path:
                if objname:
                    storage_path += '/' + objname
                request.environ['PATH_INFO'] = '/%s%s' % (version, storage_path)
        return self.app


def filter_factory(global_conf, **local_conf):
    """Returns a WSGI filter app for use with paste.deploy."""
    conf = global_conf.copy()
    conf.update(local_conf)
    def containeralias_filter(app):
        return ContainerAliasMiddleware(app, conf)
    return containeralias_filter
