import json
from functools import partial

import pytest
import tornado

from graphene_tornado.graphql_extension import GraphQLExtension
from graphene_tornado.schema import schema
from graphene_tornado.tests.http_helper import HttpHelper
from graphene_tornado.tests.test_graphql import url_string, GRAPHQL_HEADER, response_json
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler

STARTED = []
ENDED = []


async def _track_closed(name, errors=None):
    ENDED.append(name)


class TrackingExtension(GraphQLExtension):

    async def request_started(self, request, query_string, parsed_query, operation_name, variables, context, request_context):
        phase = 'request'
        STARTED.append(phase)
        return partial(_track_closed, phase)

    async def parsing_started(self, query_string):
        phase = 'parsing'
        STARTED.append(phase)
        return partial(_track_closed, phase)

    async def validation_started(self):
        phase = 'validation'
        STARTED.append(phase)
        return partial(_track_closed, phase)

    async def execution_started(self, schema, document, root, context, variables, operation_name, request_context):
        phase = 'execution'
        STARTED.append(phase)
        return partial(_track_closed, phase)

    async def will_resolve_field(self, root, info, **args):
        phase = 'resolve_field'
        STARTED.append(phase)
        return partial(_track_closed, phase)

    async def will_send_response(self, response, context):
        phase = 'response'
        STARTED.append(phase)


class ExampleExtensionsApplication(tornado.web.Application):

    def __init__(self):
        handlers = [
            (r'/graphql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, extensions=[TrackingExtension()])),
            (r'/graphql/batch', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, batch=True)),
            (r'/graphql/graphiql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema))
        ]
        tornado.web.Application.__init__(self, handlers)


@pytest.fixture
def app():
    return ExampleExtensionsApplication()


@pytest.fixture
def http_helper(http_client, base_url):
    return HttpHelper(http_client, base_url)


@pytest.mark.gen_test
def test_extensions_are_called_in_order(http_helper):
    response = yield http_helper.get(url_string(
        query='query helloWho($who: String){ test(who: $who) }',
        variables=json.dumps({'who': "Dolly"})
    ), headers=GRAPHQL_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello Dolly"}
    }

    assert ['request', 'parsing', 'validation', 'execution', 'resolve_field', 'response'] == STARTED
    assert ['parsing', 'validation', 'execution', 'resolve_field', 'request'] == ENDED

