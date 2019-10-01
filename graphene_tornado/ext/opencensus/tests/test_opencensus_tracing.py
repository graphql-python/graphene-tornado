import pytest
import six
import tornado
from graphql import parse
from opencensus.trace import tracer as tracer_module
from opencensus.trace.base_exporter import Exporter
from opencensus.trace.propagation.google_cloud_format import GoogleCloudFormatPropagator
from opencensus.trace.samplers import AlwaysOnSampler

from graphene_tornado.apollo_tooling.operation_id import default_engine_reporting_signature
from graphene_tornado.ext.apollo_engine_reporting.tests.schema import schema
from graphene_tornado.ext.apollo_engine_reporting.tests.test_engine_extension import QUERY
from graphene_tornado.ext.opencensus.opencensus_tracing_extension import OpenCensusExtension
from graphene_tornado.tests.http_helper import HttpHelper
from graphene_tornado.tests.test_graphql import response_json, url_string, GRAPHQL_HEADER
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler


class ExampleOpenCensusApplication(tornado.web.Application):

    def __init__(self):
        extension = lambda: OpenCensusExtension()
        handlers = [
            (r'/graphql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, extensions=[extension])),
            (r'/graphql/batch', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, batch=True)),
        ]
        tornado.web.Application.__init__(self, handlers)


@pytest.fixture
def app():
    return ExampleOpenCensusApplication()


@pytest.fixture
def http_helper(http_client, base_url):
    return HttpHelper(http_client, base_url)


@pytest.fixture
def exporter():
    exporter = CapturingExporter()
    tracer_module.Tracer(
        sampler=AlwaysOnSampler(),
        exporter=exporter,
        propagator=GoogleCloudFormatPropagator()
    )
    return exporter


@pytest.mark.gen_test()
def test_traces_match_query(http_helper, exporter):
    response = yield http_helper.get(url_string(query=QUERY), headers=GRAPHQL_HEADER)
    assert response.code == 200
    assert 'data' in response_json(response)

    # OpenCensus is quite ready for Python3+Tornado yet
    if six.PY3:
        return

    spans = exporter.spans

    assert spans[0][0].name == 'author'
    assert spans[0][0].parent_span_id == spans[6][0].span_id
    assert spans[1][0].name == 'aBoolean'
    assert spans[1][0].parent_span_id == spans[6][0].span_id
    assert spans[2][0].name == 'author.name'
    assert spans[2][0].parent_span_id == spans[6][0].span_id
    assert spans[3][0].name == 'author.posts'
    assert spans[3][0].parent_span_id == spans[6][0].span_id
    assert spans[4][0].name == 'author.posts.0.id'
    assert spans[4][0].parent_span_id == spans[6][0].span_id
    assert spans[5][0].name == 'author.posts.1.id'
    assert spans[5][0].parent_span_id == spans[6][0].span_id

    assert spans[6][0].name == 'gql[b5c7307ba564]'
    assert spans[6][0].parent_span_id is None
    assert spans[6][0].attributes.get('signature', None) == default_engine_reporting_signature(parse(QUERY), '')


class CapturingExporter(Exporter):

    def __init__(self):
        super(CapturingExporter, self).__init__()
        self._spans = []

    @property
    def spans(self):
        return self._spans

    def emit(self, span_datas):
        pass

    def export(self, span_datas):
        self._spans.append(span_datas)

