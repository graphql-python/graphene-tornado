import re

import pytest
import six
import tornado
from google.protobuf.json_format import MessageToJson
from graphql import parse

from graphene_tornado.ext.apollo_engine_reporting.engine_agent import EngineReportingOptions
from graphene_tornado.ext.apollo_engine_reporting.engine_extension import EngineReportingExtension
from graphene_tornado.ext.apollo_engine_reporting.tests.schema import schema
from graphene_tornado.tests.http_helper import HttpHelper
from graphene_tornado.tests.test_graphql import GRAPHQL_HEADER, url_string, response_json
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler

expected = """{
  "durationNs": "-1", 
  "endTime": "2019-09-21T19:37:09.908919Z", 
  "http": {
    "method": "GET"
  }, 
  "root": {
    "child": [
      {
        "child": [
          {
            "endTime": "-1", 
            "parentType": "User", 
            "responseName": "name", 
            "startTime": "-1", 
            "type": "String"
          }, 
          {
            "child": [
              {
                "child": [
                  {
                    "endTime": "-1", 
                    "parentType": "Post", 
                    "responseName": "id", 
                    "startTime": "-1", 
                    "type": "Int"
                  }
                ], 
                "index": 0
              }, 
              {
                "child": [
                  {
                    "endTime": "-1", 
                    "parentType": "Post", 
                    "responseName": "id", 
                    "startTime": "-1", 
                    "type": "Int"
                  }
                ], 
                "index": 1
              }
            ], 
            "endTime": "-1", 
            "parentType": "User", 
            "responseName": "posts", 
            "startTime": "-1", 
            "type": "[Post]"
          }
        ], 
        "endTime": "-1", 
        "parentType": "Query", 
        "responseName": "author", 
        "startTime": "-1", 
        "type": "User"
      }, 
      {
        "endTime": "-1", 
        "parentType": "Query", 
        "responseName": "aBoolean", 
        "startTime": "-1", 
        "type": "Boolean"
      }
    ], 
    "endTime": "-1", 
    "startTime": "-1"
  }, 
  "startTime": "2019-09-21T19:37:09.908919Z"
}"""


QUERY = """
    query {
      author(id: 5) {
        name
        posts(limit: 2) {
          id
        }
      }
      aBoolean
    }
"""


engine_options = EngineReportingOptions(api_key='test')

traces = []


async def add_trace(operation_name, document_ast, query_string, trace):
    traces.append((operation_name, document_ast, query_string, trace))


class ExampleEngineReportingApplication(tornado.web.Application):

    def __init__(self):
        engine_extension = lambda: EngineReportingExtension(engine_options, add_trace)
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


@pytest.mark.gen_test()
def test_can_send_report_to_engine(http_helper):
    response = yield http_helper.get(url_string(query=QUERY), headers=GRAPHQL_HEADER)
    assert response.code == 200
    assert 'data' in response_json(response)

    assert len(traces) == 1
    operation_name, document_ast, query_string, trace = traces[0]

    assert QUERY == query_string
    assert parse(QUERY) == document_ast
    assert '' == operation_name

    trace_json = MessageToJson(trace, sort_keys=True)
    trace_json = re.sub(r'"([0-9]+)"', '"-1"', trace_json)
    trace_json = re.sub(r'"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d+Z"',
                        '"2019-09-21T19:37:09.908919Z"',
                        trace_json)

    e = expected
    if six.PY3:
        e = re.sub(r'\s+\n', '\n', expected)
    assert e == trace_json
