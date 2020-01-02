from __future__ import absolute_import

import gzip

import pytest
import six
import tornado
from graphql import parse
from six import StringIO, BytesIO

from graphene_tornado.apollo_tooling.operation_id import default_engine_reporting_signature
from graphene_tornado.ext.apollo_engine_reporting.engine_agent import EngineReportingAgent, EngineReportingOptions, \
    SERVICE_HEADER_DEFAULTS
from graphene_tornado.ext.apollo_engine_reporting.engine_extension import EngineReportingExtension
from graphene_tornado.ext.apollo_engine_reporting.reports_pb2 import FullTracesReport
from graphene_tornado.ext.apollo_engine_reporting.tests.schema import schema
from graphene_tornado.ext.apollo_engine_reporting.tests.test_engine_extension import QUERY
from graphene_tornado.tests.http_helper import HttpHelper
from graphene_tornado.tests.test_graphql import response_json, url_string, GRAPHQL_HEADER
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler


class RecordingEngineReportingAgent(EngineReportingAgent):

    def __init__(self, options, schema_hash):
        EngineReportingAgent.__init__(self, options, schema_hash)
        self.data = []

    async def post_data(self, data):
        self.data.append(data)

    def reset(self):
        self.data = []


engine_options = EngineReportingOptions(api_key='test')
agent = RecordingEngineReportingAgent(engine_options, "hash")


class ExampleEngineReportingApplication(tornado.web.Application):

    def __init__(self):
        engine_extension = lambda: EngineReportingExtension(engine_options, agent.add_trace)
        handlers = [
            (r'/graphql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, extensions=[engine_extension])),
            (r'/graphql/batch', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, batch=True)),
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
    query_key = '# -\n' + default_engine_reporting_signature(parse(QUERY), '')
    assert query_key == key
    assert report.traces_per_query[query_key].trace.pop()

    assert response.code == 200
    assert 'data' in response_json(response)


def _deserialize(message):
    fileobj = BytesIO(message) if six.PY3 else StringIO(message)
    content = gzip.GzipFile(fileobj=fileobj).read()
    return FullTracesReport.FromString(content)
