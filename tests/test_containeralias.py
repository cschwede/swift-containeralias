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

import unittest

from swift.common.swob import Request

from alias import middleware as alias


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
        
        return []


class TestContainerAlias(unittest.TestCase):
    def setUp(self, *_args, **_kwargs):
        self.app = alias.AliasMiddleware(FakeApp(), {})
        self.cache = FakeCache({
            'container/a/c': {'meta': {'alias': '/v1/a2/c2'}},
        })

    def test_get_container(self):
        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'GET',
                                     'swift.cache': self.cache,
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a2/c2')
        self.assertEquals(res.environ['RAW_PATH_INFO'], '/v1/a2/c2')
        self.assertEquals(res.status_int, 200)

    def test_get_object(self):
        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'GET',
                                     'swift.cache': self.cache,
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a2/c2/o')
        self.assertEquals(res.environ['RAW_PATH_INFO'], '/v1/a2/c2/o')
        self.assertEquals(res.status_int, 200)

    def test_set_alias_empty_container(self):
        cache = FakeCache()

        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'POST',
                                     'HTTP_X_CONTAINER_META_ALIAS': 'a',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEquals(res.status_int, 200)

    def test_set_alias_container_with_object(self):
        cache = FakeCache({'container/a/c': {'object_count': '1'}})
        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'POST',
                                     'HTTP_X_CONTAINER_META_ALIAS': 'a',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEquals(res.status_int, 400)

    def test_delete_container(self):
        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'DELETE',
                                     'swift.cache': self.cache,
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEquals(res.status_int, 200)

    def test_delete_object(self):
        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'DELETE',
                                     'swift.cache': self.cache,
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a2/c2/o')
        self.assertEquals(res.status_int, 200)

    def test_head_container(self):
        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'HEAD',
                                     'swift.cache': self.cache,
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEquals(res.status_int, 200)

    def test_head_object(self):
        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'HEAD',
                                     'swift.cache': self.cache,
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a2/c2/o')
        self.assertEquals(res.status_int, 200)


class TestObjectAlias(unittest.TestCase):
    def setUp(self, *_args, **_kwargs):
        self.app = alias.AliasMiddleware(FakeApp(), {})
        self.cache = FakeCache()

    def test_get_object(self):
        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'GET',
                                     'swift.cache': self.cache,
                                     'swift.object/a/c/o': {
                                        'meta': {
                                            'alias': '/v1/a2/c2/o2'}},
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a2/c2/o2')
        self.assertEquals(res.environ['RAW_PATH_INFO'], '/v1/a2/c2/o2')
        self.assertEquals(res.status_int, 200)

    def test_delete_object(self):
        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'DELETE',
                                     'swift.cache': self.cache,
                                     'swift.object/a/c/o': {
                                        'meta': {
                                            'alias': '/v1/a2/c2/o2'}},
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c/o')
        self.assertEquals(res.status_int, 200)

    def test_head_object(self):
        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'HEAD',
                                     'swift.cache': self.cache,
                                     'swift.object/a/c/o': {
                                        'meta': {
                                            'alias': '/v1/a2/c2/o2'}},
                                     })
        res = req.get_response(self.app)
        self.assertEquals(res.environ['PATH_INFO'], '/v1/a/c/o')
        self.assertEquals(res.status_int, 200)


if __name__ == '__main__':
    unittest.main()
