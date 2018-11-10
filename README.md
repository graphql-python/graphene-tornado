[![Build Status](https://travis-ci.org/graphql-python/graphene-tornado.svg?branch=master)](https://travis-ci.org/graphql-python/graphene-tornado) 
[![Coverage Status](https://coveralls.io/repos/github/graphql-python/graphene-tornado/badge.svg?branch=master)](https://coveralls.io/github/graphql-python/graphene-tornado?branch=master)

# graphene-tornado

A project for running [Graphene](http://graphene-python.org/) on top of [Tornado](http://www.tornadoweb.org/) in Python 2 and 3. The codebase is a port of [graphene-django](https://github.com/graphql-python/graphene-django).

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
