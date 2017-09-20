import json
import urllib

from tornado.testing import AsyncHTTPTestCase

from examples.example import ExampleApplication


class BaseTestCase(AsyncHTTPTestCase):

    def get_app(self):
        self.app = ExampleApplication()
        return self.app

    def setUp(self):
        pass
        super(BaseTestCase, self).setUp()

    def get(self, url, **kwargs):
        return self.http_client.fetch(self.get_url(url), **kwargs)

    def delete(self, url, **kwargs):
        kwargs['method'] = kwargs.get('method', 'DELETE')
        return self.get(url, **kwargs)

    def post(self, url, post_data, **kwargs):
        kwargs['method'] = kwargs.get('method', 'POST')
        kwargs['body'] = urllib.urlencode(post_data)
        return self.get(url, **kwargs)

    def post_body(self, url, **kwargs):
        kwargs['method'] = kwargs.get('method', 'POST')
        return self.http_client.fetch(self.get_url(url), **kwargs)

    def post_json(self, url, post_data, **kwargs):
        kwargs['method'] = kwargs.get('method', 'POST')
        kwargs['body'] = json.dumps(post_data)
        kwargs['headers'] = kwargs.get('headers', {})
        kwargs['headers']['Content-Type'] = "application/json"
        return self.get(url, **kwargs)

    def put(self, url, put_data, **kwargs):
        kwargs['method'] = kwargs.get('method', 'PUT')
        return self.post(url, put_data, **kwargs)

    def get_url(self, path):
        return '%s://localhost:%s%s' % (self.get_protocol(),
                self.get_http_port(), path)
