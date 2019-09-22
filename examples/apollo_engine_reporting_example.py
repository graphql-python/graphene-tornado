import tornado
from tornado.ioloop import IOLoop

from graphene_tornado.schema import schema
from graphene_tornado.ext.apollo_engine_reporting import EngineReportingOptions, EngineReportingAgent
from graphene_tornado.ext.apollo_engine_reporting.engine_extension import EngineReportingExtension
from graphene_tornado.ext.apollo_engine_reporting.schema_utils import generate_schema_hash
from graphene_tornado.tornado_graphql_handler import TornadoGraphQLHandler

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


if __name__ == '__main__':
    app = ExampleEngineReportingApplication()
    app.listen(5000)
    IOLoop.instance().start()
