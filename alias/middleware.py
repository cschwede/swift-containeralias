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
``alias`` is a middleware which redirects requests to a different
container or object given by the ``x-(container|object)-meta-alias``
metadata entry. The target can also reside within another account.

The ``alias`` middleware should be added to the pipeline in your
``/etc/swift/proxy-server.conf`` file.
For example::

[pipeline:main]
pipeline = catch_errors cache tempauth alias proxy-server

[filter:alias]
use = egg:alias#alias

"""

from swift.common.swob import wsgify, HTTPBadRequest
from swift.common.utils import split_path
from swift.proxy.controllers.base import get_container_info, get_object_info


class AliasMiddleware(object):
    """ Alias middleware

    See above for a full description.

    """

    def __init__(self, app, conf, *args, **kwargs):
        self.app = app

    @wsgify
    def __call__(self, request):
        try:
            (version, account, container, object_name) = split_path(
                                  request.path_info, 1, 4, True)
        except ValueError:
            return self.app(environ, start_response)

        if container:
            if not object_name:
                # DELETE+HEAD to container itself, not the alias
                if request.method in ('DELETE', 'HEAD'):
                    return self.app

                if request.method == 'POST':
                    # Deny setting if there are any objects in base container
                    # Otherwise these objects won't be visible
                    if request.headers.get('X-Container-Meta-Alias'):
                        container_info = get_container_info(request.environ, self.app)
                        objects = container_info.get('object_count')
                        if objects and int(objects) > 0:
                            return HTTPBadRequest()

            container_info = get_container_info(request.environ, self.app)
            container_alias = container_info.get('meta', {}).get('alias')
            if container_alias:
                if object_name:
                    container_alias += '/' + object_name
                request.environ['PATH_INFO'] = container_alias
                request.environ['RAW_PATH_INFO'] = container_alias

            if object_name:
                # DELETE+HEAD will access original object, not object alias points to
                if request.method in ('DELETE', 'HEAD'):
                    return self.app

                object_info = get_object_info(request.environ, self.app)
                object_alias = object_info.get('meta', {}).get('alias')
                if object_alias:
                    request.environ['PATH_INFO'] = object_alias
                    request.environ['RAW_PATH_INFO'] = object_alias

        return self.app


def filter_factory(global_conf, **local_conf):
    """Returns a WSGI filter app for use with paste.deploy."""
    conf = global_conf.copy()
    conf.update(local_conf)
    def alias_filter(app):
        return AliasMiddleware(app, conf)
    return alias_filter
