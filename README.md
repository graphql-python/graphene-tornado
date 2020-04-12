[![Build Status](https://travis-ci.org/graphql-python/graphene-tornado.svg?branch=master)](https://travis-ci.org/graphql-python/graphene-tornado) 
[![Coverage Status](https://coveralls.io/repos/github/graphql-python/graphene-tornado/badge.svg?branch=master)](https://coveralls.io/github/graphql-python/graphene-tornado?branch=master)

# graphene-tornado

A project for running [Graphene](http://graphene-python.org/) on top of [Tornado](http://www.tornadoweb.org/) for Python 3. The codebase was originally a port of [graphene-django](https://github.com/graphql-python/graphene-django).

# Getting started

Create a Tornado application and add the GraphQL handlers:

```python
import tornado.web
from tornado.ioloop import IOLoop

from graphene_tornado.schema import schema
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler


class ExampleApplication(tornado.web.Application):

    def __init__(self):
        handlers = [
            (r'/graphql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema)),
            (r'/graphql/batch', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, batch=True)),
            (r'/graphql/graphiql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema))
        ]
        tornado.web.Application.__init__(self, handlers)

if __name__ == '__main__':
    app = ExampleApplication()
    app.listen(5000)
    IOLoop.instance().start()
```

When writing your resolvers, decorate them with either Tornado's `@coroutine` decorator for Python 2.7:

```python
@gen.coroutine
def resolve_foo(self, info):
  foo = yield db.get_foo()
  raise Return(foo)
```

Or use the `async` / `await` pattern in Python 3:

```python
async def resolve_foo(self, info):
  foo = await db.get_foo()
  return foo
```

# Extensions

`graphene-tornado` supports server-side extensions like [Apollo Server](https://www.apollographql.com/docs/apollo-server/features/metrics). The extensions go a step further than Graphene middleware to allow for finer grained interception of request processing. The canonical use case is for tracing; see `graphene_tornado/apollo_engine_reporting/engine_agent.py` for an example.

Extensions are experimental and most likely will change in future releases as they should be extensions provided by 
`graphql-server-core`.

## Apollo Engine Reporting

You can integrate with Apollo Engine Reporting by enabling the extension.

```console
$ pip install graphene-tornado[apollo-engine-reporting]
```

```python
engine_options = EngineReportingOptions()
agent = EngineReportingAgent(engine_options, generate_schema_hash(schema))


class ExampleEngineReportingApplication(tornado.web.Application):

    def __init__(self):
        engine_extension = lambda: EngineReportingExtension(engine_options, agent.add_trace)
        handlers = [
            (r'/graphql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, extensions=[engine_extension])),
            (r'/graphql/batch', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, batch=True, 
                                                            extensions=[engine_extension])),
            (r'/graphql/graphiql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, 
                                                               extensions=[engine_extension]))
        ]
        tornado.web.Application.__init__(self, handlers)
```


```console
ENGINE_API_KEY=<your engine API key here> python -m examples.apollo_engine_reporting_example
```

Then visit `http://localhost:5000/graphql/graphiql`, make some queries, and view the results in Apollo Engine.

## OpenCensus

You can also use [OpenCensus](https://github.com/census-instrumentation/opencensus-python) for tracing:

```console
$ pip install graphene-tornado[opencensus]
```


```python
class ExampleOpenCensusApplication(tornado.web.Application):

    def __init__(self):
        extension = lambda: OpenCensusExtension()
        handlers = [
            (r'/graphql', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, extensions=[extension])),
            (r'/graphql/batch', TornadoGraphQLHandler, dict(graphiql=True, schema=schema, batch=True)),
        ]
        tornado.web.Application.__init__(self, handlers)
```
