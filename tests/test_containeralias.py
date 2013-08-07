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

import json
import unittest

from swift.common.swob import Request

from containeralias import middleware as containeralias


class FakeCache(object):
    def __init__(self, val=None):
        if val:
            self.val = val
        else:
            self.val = {}

    def get(self, key, *args):
        return self.val.get(key)

    def set(self, *args, **kwargs):
        pass


class FakeApp(object):
    def __init__(self, headers=None):
        if headers:
            self.headers = headers
        else:
            self.headers = {}

    def __call__(self, env, start_response):
        start_response('200 OK', self.headers)
        
        path = env.get('PATH_INFO')
        if path == '/v1/AUTH_.auth/account1/.services':
            return json.dumps({'storage': {
                'cluster_name': 'http://localhost/v1/AUTH_123'}})
        return []

class FakeBadApp(object):
    def __init__(self, headers=None):
        if headers:
            self.headers = headers
        else:
            self.headers = {}

    def __call__(self, env, start_response):
        start_response('200 OK', self.headers)
        return []


def start_response(*args):
    pass


class TestContainerAlias(unittest.TestCase):

    def test_redirect(self):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache({
            'container/a/c': {'meta': {'storage-path': '/v1/a2/c2'}},
        })

        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'GET',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a2/c2')
        self.assertEquals(res.environ['RAW_PATH_INFO'], '/v1/a2/c2')
        self.assertEquals(res.status_int, 200)

        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'GET',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a2/c2/o')
        self.assertEquals(res.environ['RAW_PATH_INFO'], '/v1/a2/c2/o')
        self.assertEquals(res.status_int, 200)

    def test_container_post(self):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache()

        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'POST',
                                     'HTTP_X_CONTAINER_META_STORAGE_PATH': 'a',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEquals(res.status_int, 200)

        cache = FakeCache({'container/a/c': {'object_count': '1'}})
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'POST',
                                     'HTTP_X_CONTAINER_META_STORAGE_PATH': 'a',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEquals(res.status_int, 400)

    def test_container_delete(self):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache({
            'container/a/c': {'meta': {'storage-path': '/v1/a2/c2'}},
        })

        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'DELETE',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEquals(res.status_int, 200)

        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'DELETE',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a2/c2/o')
        self.assertEquals(res.status_int, 200)

    def test_container_head(self):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache({
            'container/a/c': {'meta': {'storage-path': '/v1/a2/c2'}},
        })

        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'HEAD',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEquals(res.status_int, 200)

    def test_container_post_acl(self):
        conf = {'auth_method': 'swauth'}
        app = containeralias.ContainerAliasMiddleware(FakeApp(), conf)
        cache = FakeCache()

        req = Request.blank('/v1/AUTH_test/container',
                            environ={'REQUEST_METHOD': 'POST',
                                     'HTTP_X_CONTAINER_READ': 'account1,account2:user',
                                     'REMOTE_USER': 'account:user,account',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEquals(res.status_int, 200)


if __name__ == '__main__':
    unittest.main()
