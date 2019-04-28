from __future__ import absolute_import

import gzip
from six import StringIO

import pytest
import tornado
from graphql import build_ast_schema, parse
from tornado.gen import coroutine

from graphene_tornado.apollo_engine_reporting.engine_agent import EngineReportingAgent, EngineReportingOptions, \
    SERVICE_HEADER_DEFAULTS
from graphene_tornado.apollo_engine_reporting.engine_extension import EngineReportingExtension
from graphene_tornado.apollo_engine_reporting.reports_pb2 import FullTracesReport
from graphene_tornado.apollo_engine_reporting.tests.test_engine_extension import SCHEMA_STRING, QUERY
from graphene_tornado.tests.http_helper import HttpHelper
from graphene_tornado.tests.test_graphql import response_json, url_string, GRAPHQL_HEADER
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler

SCHEMA = build_ast_schema(parse(SCHEMA_STRING))


class RecordingEngineReportingAgent(EngineReportingAgent):

    def __init__(self, options, schema_hash):
        EngineReportingAgent.__init__(self, options, schema_hash)
        self.data = []

    @coroutine
    def post_data(self, data):
        self.data.append(data)

    def reset(self):
        self.data = []


engine_options = EngineReportingOptions(api_key='test')
agent = RecordingEngineReportingAgent(engine_options, "hash")


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


@pytest.fixture(scope="function", autouse=True)
def reset():
    yield
    agent.reset()


@pytest.mark.gen_test
def test_can_send_report_to_engine(http_helper):
    response = yield http_helper.get(url_string(query=QUERY), headers=GRAPHQL_HEADER)

    report = _deserialize(agent.data[0])

    assert report.header.hostname == SERVICE_HEADER_DEFAULTS.get('hostname')
    assert report.header.agent_version == SERVICE_HEADER_DEFAULTS.get('agentVersion')
    assert report.header.runtime_version == SERVICE_HEADER_DEFAULTS.get('runtimeVersion')
    assert report.header.uname == SERVICE_HEADER_DEFAULTS.get('uname')

    assert len(report.traces_per_query) == 1
    key = next(iter(report.traces_per_query))
    query_key = '# -\n' + QUERY
    assert query_key == key
    assert report.traces_per_query[query_key].trace.pop()

    assert response.code == 200
    assert 'data' in response_json(response)


def _deserialize(message):
    content = gzip.GzipFile(fileobj=StringIO(message)).read()
    return FullTracesReport.FromString(content)
