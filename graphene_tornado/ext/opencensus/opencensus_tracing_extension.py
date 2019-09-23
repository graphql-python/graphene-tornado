from __future__ import absolute_import

import json

from graphene_tornado.apollo_tooling.operation_id import default_engine_reporting_signature
from graphene_tornado.extension_stack import GraphQLExtension
from opencensus.trace import execution_context
from tornado.gen import Return, coroutine


class OpenCensusExtension(GraphQLExtension):

    def __init__(self):
        self.operation_name = None
        self.query_string = None
        self.document = None

    @coroutine
    def request_started(self, request, query_string, parsed_query, operation_name, variables, context, request_context):
        self.query_string = query_string
        self.document = parsed_query

        tracer = execution_context.get_opencensus_tracer()
        tracer.start_span('gql')

        @coroutine
        def on_request_ended(erors):
            op_name = self.operation_name or ''
            if self.document:
                calculate_signature = default_engine_reporting_signature
                signature = calculate_signature(self.document.document_ast, op_name)
            elif self.query_string:
                signature = self.query_string

            tracer.add_attribute_to_current_span('gql_operation_name', op_name)
            tracer.add_attribute_to_current_span('signature', signature)
            tracer.end_span()

        raise Return(on_request_ended)

    @coroutine
    def parsing_started(self, query_string):
        pass

    @coroutine
    def validation_started(self):
        pass

    @coroutine
    def execution_started(self, schema, document, root, context, variables, operation_name):
        if operation_name:
            self.operation_name = operation_name
        self.document = document

    @coroutine
    def will_resolve_field(self, root, info, **args):
        if not self.operation_name:
            self.operation_name = '' if not info.operation.name else info.operation.name.value

        tracer = execution_context.get_opencensus_tracer()

        # If we wanted to be fancy, we could build up a tree like the ApolloEngineExtension does so that the
        # whole tree appears as nested spans. However, this is a bit tricky to do with the current OpenCensus
        # API because when you request a span, a bunch of context variables are set. This keeps it simple for now.
        tracer.start_span('.'.join(str(x) for x in info.path))

        @coroutine
        def on_end(errors=None, result=None):
            tracer.end_span()

        raise Return(on_end)

    @coroutine
    def will_send_response(self, response, context):
        if hasattr(response, 'errors'):
            errors = response.errors
            for error in errors:
                error_info = {
                    'message': str(error),
                    'json': error
                }

                tracer = execution_context.get_opencensus_tracer()
                tracer.add_attribute_to_current_span('gql_error', json.dumps(error_info))
