from __future__ import absolute_import, division, print_function

import json

from six.moves.urllib.parse import urlencode


class HttpHelper:

    def __init__(self, http_client, base_url):
        self.http_client = http_client
        self.base_url = base_url

    def get(self, url, **kwargs):
        return self.http_client.fetch(self.get_url(url), **kwargs)

    def delete(self, url, **kwargs):
        kwargs['method'] = kwargs.get('method', 'DELETE')
        return self.get(url, **kwargs)

    def post(self, url, post_data, **kwargs):
        kwargs['method'] = kwargs.get('method', 'POST')
        kwargs['body'] = urlencode(post_data)
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
        return self.base_url + path
