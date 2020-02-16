from typing import Optional, Any, List, Union, Callable

import pytest
import tornado
from graphql import parse, GraphQLBackend
from opencensus.trace import tracer as tracer_module, execution_context
from opencensus.trace.base_exporter import Exporter
from opencensus.trace.propagation.google_cloud_format import GoogleCloudFormatPropagator
from opencensus.trace.samplers import AlwaysOnSampler

from graphene_tornado.apollo_tooling.operation_id import default_engine_reporting_signature
from graphene_tornado.ext.apollo_engine_reporting.tests.schema import schema
from graphene_tornado.ext.apollo_engine_reporting.tests.test_engine_extension import QUERY
from graphene_tornado.ext.opencensus.opencensus_tracing_extension import OpenCensusExtension
from graphene_tornado.graphql_extension import GraphQLExtension
from graphene_tornado.tests.http_helper import HttpHelper
from graphene_tornado.tests.test_graphql import response_json, url_string, GRAPHQL_HEADER
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler


class GQLHandler(TornadoGraphQLHandler):

    def initialize(self, schema=None, executor=None, middleware: Optional[Any] = None, root_value: Any = None,
                   graphiql: bool = False, pretty: bool = False, batch: bool = False, backend: GraphQLBackend = None,
                   extensions: List[Union[Callable[[], GraphQLExtension], GraphQLExtension]] = None,
                   exporter=None):
        super().initialize(schema, executor, middleware, root_value, graphiql, pretty, batch, backend, extensions)
        execution_context.set_opencensus_tracer(tracer_module.Tracer(
                sampler=AlwaysOnSampler(),
                exporter=exporter,
                propagator=GoogleCloudFormatPropagator()
            )
        )

    def on_finish(self) -> None:
        tracer = execution_context.get_opencensus_tracer()
        tracer.finish()


class ExampleOpenCensusApplication(tornado.web.Application):

    def __init__(self, exporter):
        extension = lambda: OpenCensusExtension()
        handlers = [
            (r'/graphql', GQLHandler, dict(graphiql=True, schema=schema, extensions=[extension], exporter=exporter)),
        ]
        tornado.web.Application.__init__(self, handlers)


@pytest.fixture
def app(exporter):
    return ExampleOpenCensusApplication(exporter)


@pytest.fixture
def app(exporter):
    return ExampleOpenCensusApplication(exporter)


@pytest.fixture
def http_helper(http_client, base_url):
    return HttpHelper(http_client, base_url)


@pytest.fixture
def exporter():
    return CapturingExporter()


@pytest.mark.gen_test()
def test_traces_match_query(http_helper, exporter):
    response = yield http_helper.get(url_string(query=QUERY), headers=GRAPHQL_HEADER)
    assert response.code == 200
    assert 'data' in response_json(response)

    parent = exporter.spans.pop()[0]

    assert parent.name == 'gql[b5c7307ba564]'
    assert parent.parent_span_id is None
    assert parent.attributes.get('signature', None) == default_engine_reporting_signature(parse(QUERY), '')

    spans = [span for span_list in exporter.spans for span in span_list]

    expected = [
        'gql_parsing',
        'gql_validation',
        'author',
        'aBoolean',
        'author.name',
        'author.posts',
        'author.posts.0.id',
        'author.posts.1.id'
    ]
    
    for span, exp in zip(spans, expected):
        assert span.name == exp
        assert span.parent_span_id == parent.span_id


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

