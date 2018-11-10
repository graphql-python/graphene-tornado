from __future__ import absolute_import, division, print_function

import pytest
from tornado.escape import to_unicode

from examples.example import ExampleApplication
from graphene_tornado.tests.http_helper import HttpHelper


class Unset(object):
    pass


@pytest.fixture
def app():
    return ExampleApplication()


@pytest.fixture
def http_helper(http_client, base_url):
    return HttpHelper(http_client, base_url)


@pytest.mark.gen_test
def test_displays_graphiql_with_direct_route(http_helper):
    res = yield http_helper.get('/graphql/graphiql', headers={'Accept': 'text/html'})
    has_graphiql(res)


@pytest.mark.gen_test
def test_displays_graphiql_with_accept_html(http_helper):
    res = yield http_helper.get('/graphql/graphiql', headers={'Accept': 'text/html'})
    has_graphiql(res)


@pytest.mark.gen_test
def test_graphiql_is_enabled(http_helper):
    res = yield http_helper.get('/graphql', headers={'Accept': 'text/html'})
    has_graphiql(res)


@pytest.mark.gen_test
def test_graphiql_default_title(http_helper):
    res = yield http_helper.get('/graphql', headers={'Accept': 'text/html'})
    assert '<title>GraphiQL</title>' in to_unicode(res.body)


@pytest.mark.gen_test
def test_graphiql_renders_pretty(http_helper):
    response = yield http_helper.get('/graphql?query={test}', headers={'Accept': 'text/html'})
    pretty_response = (
        '{\n'
        '  "data": {\n'
        '    "test": "Hello World"\n'
        '  }\n'
        '}'
    ).replace("\"", "\\\"").replace("\n", "\\n")
    assert pretty_response in to_unicode(response.body)


@pytest.mark.gen_test
def test_graphiql_renders_pretty(http_helper):
    response = yield http_helper.get('/graphql?query={test}', headers={'Accept': 'text/html'})
    pretty_response = (
        '{\n'
        '  "data": {\n'
        '    "test": "Hello World"\n'
        '  }\n'
        '}'
    ).replace("\"", "\\\"").replace("\n", "\\n")
    assert pretty_response in to_unicode(response.body)


@pytest.mark.gen_test
def test_handles_empty_vars(http_helper):
    response = yield http_helper.post_json('/graphql', headers={'Accept': 'text/html'}, post_data=dict(
        query="",
        variables=None,
        operationName=""
    ))
    has_graphiql(response)


def has_graphiql(response):
    assert "ReactDOM" in to_unicode(response.body)
    assert response.code == 200
