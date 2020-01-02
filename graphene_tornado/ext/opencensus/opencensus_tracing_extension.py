from __future__ import absolute_import

import json

from opencensus.trace import execution_context
from tornado.gen import Return, coroutine

from graphene_tornado.apollo_tooling.query_hash import compute
from graphene_tornado.ext.extension_helpers import get_signature
from graphene_tornado.extension_stack import GraphQLExtension
from graphene_tornado.request_context import SIGNATURE_HASH_KEY


class OpenCensusExtension(GraphQLExtension):

    def __init__(self):
        self.operation_name = None
        self.query_string = None
        self.document = None

    async def request_started(self, request, query_string, parsed_query, operation_name, variables, context, request_context):
        self.query_string = query_string
        self.document = parsed_query

        tracer = execution_context.get_opencensus_tracer()
        tracer.start_span('gql')

        async def on_request_ended(errors):
            op_name = self.operation_name or ''
            document = request_context.get('document', None)
            signature = get_signature(request_context, operation_name, document, query_string)

            tracer = execution_context.get_opencensus_tracer()
            if SIGNATURE_HASH_KEY not in request_context:
                request_context[SIGNATURE_HASH_KEY] = compute(signature)
            tracer.current_span().name = 'gql[{}]'.format(request_context[SIGNATURE_HASH_KEY][0:12])

            tracer.add_attribute_to_current_span('gql_operation_name', op_name)
            tracer.add_attribute_to_current_span('signature', signature)
            tracer.end_span()

        return on_request_ended

    async def parsing_started(self, query_string):
        pass

    async def validation_started(self):
        pass

    async def execution_started(self, schema, document, root, context, variables, operation_name, request_context):
        if operation_name:
            self.operation_name = operation_name
        request_context['document'] = document

    async def will_resolve_field(self, root, info, **args):
        if not self.operation_name:
            self.operation_name = '' if not info.operation.name else info.operation.name.value

        tracer = execution_context.get_opencensus_tracer()

        # If we wanted to be fancy, we could build up a tree like the ApolloEngineExtension does so that the
        # whole tree appears as nested spans. However, this is a bit tricky to do with the current OpenCensus
        # API because when you request a span, a bunch of context variables are set. This keeps it simple for now.
        tracer.start_span('.'.join(str(x) for x in info.path))

        async def on_end(errors=None, result=None):
            tracer.end_span()

        return on_end

    async def will_send_response(self, response, context):
        if hasattr(response, 'errors'):
            errors = response.errors
            for error in errors:
                error_info = {
                    'message': str(error),
                    'json': error
                }

                tracer = execution_context.get_opencensus_tracer()
                tracer.add_attribute_to_current_span('gql_error', json.dumps(error_info))
