from google.protobuf.json_format import MessageToJson
from graphql import get_default_backend, parse, build_ast_schema, execute
from tornado.gen import coroutine
from tornado.httpserver import HTTPRequest

from graphene_tornado.apollo_engine_reporting.engine_agent import EngineReportingOptions
from graphene_tornado.apollo_engine_reporting.engine_extension import EngineReportingExtension, CLIENT_NAME_HEADER
from graphene_tornado.extension_stack import GraphQLExtensionStack
from graphene_tornado.tornado_executor import TornadoExecutor

expected = """
    {
        "durationNs": "9057355",      
        "startTime": "2019-04-28T06:46:48.570056Z", 
        "endTime": "2019-04-28T06:46:52.735232Z", 
        "clientName": "graphene_tornado",
        "http": {
          "method": "POST"
        },
        "root": {
          "child": [
            {
              "parentType": "Query",
              "fieldName": "author",
              "type": "User",
              "startTime": "7193813",
              "endTime": "7489762",
              "child": [
                {
                  "fieldName": "name",
                  "type": "String",
                  "startTime": "7873189",
                  "endTime": "7923741",
                  "parentType": "User"
                },
                {
                  "fieldName": "posts",
                  "type": "[Post]",
                  "startTime": "8120404",
                  "endTime": "8150491",
                  "child": [
                    {
                      "index": 0,
                      "child": [
                        {
                          "fieldName": "id",
                          "type": "Int",
                          "startTime": "8369440",
                          "endTime": "8413906",
                          "parentType": "Post"
                        }
                      ]
                    },
                    {
                      "index": 1,
                      "child": [
                        {
                          "fieldName": "id",
                          "type": "Int",
                          "startTime": "8649354",
                          "endTime": "8676716",
                          "parentType": "Post"
                        }
                      ]
                    }
                  ],
                  "parentType": "User"
                }
              ]
            },
            {
              "fieldName": "aBoolean",
              "type": "Boolean",
              "startTime": "8703508",
              "endTime": "8727397",
              "parentType": "Query"
            }
          ]
        }
      }
"""

SCHEMA_STRING = """
  schema {
      query: Query
  }
  
  type User {
    id: Int
    name: String
    posts(limit: Int): [Post]
  }
  type Post {
    id: Int
    title: String
    views: Int
    author: User
  }
  type Query {
    aString: String
    aBoolean: Boolean
    anInt: Int
    author(id: Int): User
    topPosts(limit: Int): [Post]
  }
"""

QUERY = """
    query q {
      author(id: 5) {
        name
        posts(limit: 2) {
          id
        }
      }
      aBoolean
    }
"""


@coroutine
def test_trace():
    traces = []

    @coroutine
    def add_trace(signature, operation_name, trace):
        traces.append((signature, operation_name, trace))

    ext = EngineReportingExtension(EngineReportingOptions(), add_trace)
    stack = GraphQLExtensionStack([ext])

    request = HTTPRequest(
        method='POST', uri='/test', headers={CLIENT_NAME_HEADER: 'graphene_tornado'}, body=None
    )

    request_end = yield stack.request_started(request=request, query_string=QUERY, parsed_query=None,
                                              operation_name=None,
                                              variables=None, context=None, request_context=None)

    schema = build_ast_schema(parse(SCHEMA_STRING))
    document = get_default_backend().document_from_string(schema, QUERY)

    yield ext.execution_started(
        schema=schema,
        document=document,
        root=None,
        context=None,
        variables=None,
        operation_name='q',
    )

    result = yield execute(schema, document.document_ast, middleware=[stack.as_middleware()],
                           executor=TornadoExecutor())

    assert not result.errors

    request_end()

    assert len(traces) == 1
    signature, operation_name, trace = traces[0]

    assert QUERY == signature
    assert 'q' == operation_name
    assert expected == MessageToJson(trace, including_default_value_fields=True)
