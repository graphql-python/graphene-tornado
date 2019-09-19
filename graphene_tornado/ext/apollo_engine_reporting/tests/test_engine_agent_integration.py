import pytest
import tornado
from graphql import build_ast_schema, parse

from graphene_tornado.ext.apollo_engine_reporting.engine_agent import EngineReportingOptions, EngineReportingAgent
from graphene_tornado.ext.apollo_engine_reporting.engine_extension import EngineReportingExtension
from graphene_tornado.ext.apollo_engine_reporting.tests.schema import SCHEMA_STRING
from graphene_tornado.ext.apollo_engine_reporting.tests.test_engine_extension import QUERY
from graphene_tornado.ext.apollo_engine_reporting.schema_utils import generate_schema_hash
from graphene_tornado.tests.http_helper import HttpHelper
from graphene_tornado.tests.test_graphql import response_json, url_string, GRAPHQL_HEADER
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler

SCHEMA = build_ast_schema(parse(SCHEMA_STRING))


engine_options = EngineReportingOptions(api_key='test')
agent = EngineReportingAgent(engine_options, generate_schema_hash(SCHEMA))


class ExampleEngineReportingApplication(tornado.web.Application):

    def __init__(self):
        engine_extension = EngineReportingExtension(engine_options, agent.add_trace)
        handlers = [
            (r'/graphql', TornadoGraphQLHandler, dict(graphiql=True, schema=SCHEMA, extensions=[engine_extension])),
            (r'/graphql/batch', TornadoGraphQLHandler, dict(graphiql=True, schema=SCHEMA, batch=True)),
        ]
        tornado.web.Application.__init__(self, handlers)


@pytest.fixture
def app():
    return ExampleEngineReportingApplication()


@pytest.fixture
def http_helper(http_client, base_url):
    return HttpHelper(http_client, base_url)


@pytest.mark.gen_test()
@pytest.mark.skip()
def test_can_send_report_to_engine(http_helper):
    response = yield http_helper.get(url_string(query=QUERY), headers=GRAPHQL_HEADER)
    assert response.code == 200
    assert 'data' in response_json(response)
