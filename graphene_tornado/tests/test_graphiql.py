from hamcrest import assert_that, contains_string, equal_to
from tornado.testing import gen_test

from graphene_tornado.tests.base_test_case import BaseTestCase


class Unset(object):
    pass


class TestGraphiQL(BaseTestCase):

    @gen_test
    def test_displays_graphiql_with_direct_route(self):
        res = yield self.get('/graphql/graphiql', headers={'Accept': 'text/html'})
        self.has_graphiql(res)

    @gen_test
    def test_displays_graphiql_with_accept_html(self):
        res = yield self.get('/graphql/graphiql', headers={'Accept': 'text/html'})
        self.has_graphiql(res)

    @gen_test
    def test_graphiql_is_enabled(self):
        res = yield self.get('/graphql', headers={'Accept': 'text/html'})
        self.has_graphiql(res)

    @gen_test
    def test_graphiql_default_title(self):
        res = yield self.get('/graphql', headers={'Accept': 'text/html'})
        assert_that(res.body, contains_string('<title>GraphiQL</title>'))

    @gen_test
    def test_graphiql_renders_pretty(self):
        response = yield self.get('/graphql?query={test}', headers={'Accept': 'text/html'})
        pretty_response = (
            '{\n'
            '  "data": {\n'
            '    "test": "Hello World"\n'
            '  }\n'
            '}'
        ).replace("\"", "\\\"").replace("\n", "\\n")
        assert_that(response.body, contains_string(pretty_response))

    @gen_test
    def test_graphiql_renders_pretty(self):
        response = yield self.get('/graphql?query={test}', headers={'Accept': 'text/html'})
        pretty_response = (
            '{\n'
            '  "data": {\n'
            '    "test": "Hello World"\n'
            '  }\n'
            '}'
        ).replace("\"", "\\\"").replace("\n", "\\n")
        assert_that(response.body, contains_string(pretty_response))

    @gen_test
    def test_handles_empty_vars(self):
        response = yield self.post_json('/graphql', headers={'Accept': 'text/html'}, post_data=dict(
            query="",
            variables=None,
            operationName=""
        ))
        self.has_graphiql(response)

    def has_graphiql(self, response):
        assert_that(response.body, contains_string("ReactDOM"))
        assert_that(response.code, equal_to(200))
