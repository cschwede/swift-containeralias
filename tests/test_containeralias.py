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
import mock
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

    def test_acl_check(self):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache({
            'container/a/c': {'meta': {'storage-path': '/v1/a2/c2'}},
        })

        for method in ['GET', 'PUT', 'POST', 'COPY']:
            # DELETE and HEAD are not redirected on container level
            req = Request.blank('/v1/a/c',
                                environ={'REQUEST_METHOD': method,
                                         'swift.cache': cache,
                                         'REMOTE_USER': 'a1:u1'})
            res = req.get_response(app)
            self.assertEqual(res.status_int, 403)

        for method in ['HEAD', 'DELETE']:
            req = Request.blank('/v1/a/c/o',
                                environ={'REQUEST_METHOD': method,
                                         'swift.cache': cache,
                                         'REMOTE_USER': 'a1:u1'})
            res = req.get_response(app)
            self.assertEqual(res.status_int, 403)

    def test_acl_check_tempurl(self):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache({
            'container/AUTH_a1/c': {'meta': {'storage-path': '/v1/a2/c2'}},
            'container/a2/c2': {'read_acl': 'a1', 'write_acl': 'a1'},
        })

        for user in ['.wsgi.pre_authed', '.wsgi.tempurl']:
            for method in ['GET', 'PUT', 'POST', 'COPY']:
                # DELETE and HEAD are not redirected on container level
                req = Request.blank('/v1/AUTH_a1/c',
                                    environ={'REQUEST_METHOD': method,
                                             'swift.cache': cache,
                                             'REMOTE_USER': user})
                res = req.get_response(app)
                self.assertEqual(res.status_int, 200)

            for method in ['HEAD', 'DELETE']:
                req = Request.blank('/v1/AUTH_a1/c/o',
                                    environ={'REQUEST_METHOD': method,
                                             'swift.cache': cache,
                                             'REMOTE_USER': user})
                res = req.get_response(app)
                self.assertEqual(res.status_int, 200)

    def test_redirect(self):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache({
            'container/a/c': {'meta': {'storage-path': '/v1/a2/c2'}},
            'container/a2/c2': {'read_acl': 'a1:u1'},
        })

        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'GET',
                                     'swift.cache': cache,
                                     'REMOTE_USER': 'a1:u1',
                                     })
        res = req.get_response(app)
        self.assertEqual(res.environ['PATH_INFO'], '/v1/a2/c2')
        self.assertEqual(res.environ['RAW_PATH_INFO'], '/v1/a2/c2')
        self.assertEqual(res.status_int, 200)

        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'GET',
                                     'swift.cache': cache,
                                     'REMOTE_USER': 'a1:u1',
                                     })
        res = req.get_response(app)
        self.assertEqual(res.environ['PATH_INFO'], '/v1/a2/c2/o')
        self.assertEqual(res.environ['RAW_PATH_INFO'], '/v1/a2/c2/o')
        self.assertEqual(res.status_int, 200)

    def test_container_post(self):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache()

        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'POST',
                                     'HTTP_X_CONTAINER_META_STORAGE_PATH': 'a',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEqual(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEqual(res.status_int, 200)

        cache = FakeCache({'container/a/c': {'object_count': '1'}})
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'POST',
                                     'HTTP_X_CONTAINER_META_STORAGE_PATH': 'a',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEqual(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEqual(res.status_int, 400)

    @mock.patch.object(containeralias.ContainerAliasMiddleware,
                       '_delete_target_containers')
    def test_container_delete(self, dtc_mock):
        app = containeralias.ContainerAliasMiddleware(FakeApp(), {})
        cache = FakeCache({
            'container/a/c': {'meta': {'storage-path': '/v1/a2/c2'}},
            'container/a2/c2': {'write_acl': 'a1:u1'},
        })

        req = Request.blank('/v1/a/c',
                            environ={'REQUEST_METHOD': 'DELETE',
                                     'swift.cache': cache,
                                     'REMOTE_USER': 'a1:u1',
                                     })
        res = req.get_response(app)
        self.assertEqual(dtc_mock.call_count, 1)
        self.assertEqual(dtc_mock.call_args[0][3], set(['']))
        self.assertEqual(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEqual(res.status_int, 200)

        req = Request.blank('/v1/a/c/o',
                            environ={'REQUEST_METHOD': 'DELETE',
                                     'swift.cache': cache,
                                     'REMOTE_USER': 'a1:u1',
                                     })
        res = req.get_response(app)
        self.assertEqual(res.environ['PATH_INFO'], '/v1/a2/c2/o')
        self.assertEqual(res.status_int, 200)

        dtc_mock.reset_mock()
        cache = FakeCache({'container/a/c': {'read_acl': 'a1:u1,a1,a2:u1'}})
        req = Request.blank('/v1/a/c', environ={'REQUEST_METHOD': 'DELETE',
                                                'swift.cache': cache,
                                                })
        res = req.get_response(app)

        self.assertEqual(dtc_mock.call_count, 1)
        self.assertEqual(dtc_mock.call_args[0][3], set(['a1', 'a2']))
        self.assertEqual(res.status_int, 200)

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
        self.assertEqual(res.environ['PATH_INFO'], '/v1/a/c')
        self.assertEqual(res.status_int, 200)

    @mock.patch.object(
        containeralias.ContainerAliasMiddleware, '_create_target_containers')
    @mock.patch.object(
        containeralias.ContainerAliasMiddleware, '_delete_target_containers')
    def test_container_post_acl(self, dtc_mock, ctc_mock):
        conf = {'auth_method': 'swauth'}
        app = containeralias.ContainerAliasMiddleware(FakeApp(), conf)
        cache = FakeCache({'container/AUTH_test/container': {
            'read_acl': 'account1:user,account3'}})

        req = Request.blank('/v1/AUTH_test/container',
                            environ={'REQUEST_METHOD': 'POST',
                                     'HTTP_X_CONTAINER_READ':
                                     'account1,account2:user',
                                     'REMOTE_USER': 'account:user,account',
                                     'swift.cache': cache,
                                     })
        res = req.get_response(app)
        self.assertEqual(dtc_mock.call_args[0][3], set(['account3']))
        self.assertEqual(ctc_mock.call_args[0][4], set(['account2']))
        self.assertEqual(res.status_int, 200)


if __name__ == '__main__':
    unittest.main()
