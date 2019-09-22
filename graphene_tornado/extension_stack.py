"""
ExtensionStack is an adapter for GraphQLExtension that helps invoke a list of GraphQLExtension objects at runtime.
"""
import inspect
from functools import partial

from tornado.gen import coroutine, Return
from typing import List, Callable, Union

from graphene_tornado.graphql_extension import GraphQLExtension


def instantiate_extensions(extensions):
    for extension in extensions:
        if inspect.isclass(extension) or inspect.isfunction(extension):
            yield extension()
            continue
        yield extension


class GraphQLExtensionStack(GraphQLExtension):

    def __init__(self,
                 extensions=None  # type: List[Union[Callable[[], GraphQLExtension], GraphQLExtension]]
                 ):
        self.extensions = list(instantiate_extensions(extensions))  # type: List[GraphQLExtension]

    @coroutine
    def request_started(self, request, query_string, parsed_query, operation_name, variables, context, request_context):
        on_end = yield self._handle_did_start('request_started', request, query_string, parsed_query, operation_name,
                                              variables, context, request_context)
        raise Return(on_end)

    @coroutine
    def parsing_started(self, query_string):
        on_end = yield self._handle_did_start('parsing_started', query_string)
        raise Return(on_end)

    @coroutine
    def validation_started(self):
        on_end = yield self._handle_did_start('validation_started')
        raise Return(on_end)

    @coroutine
    def execution_started(self, schema, document, root, context, variables, operation_name):
        on_end = yield self._handle_did_start('execution_started', schema, document, root, context,
                                              variables, operation_name)
        raise Return(on_end)

    @coroutine
    def will_resolve_field(self, root, info, **args):
        ext = self.extensions[:]
        ext.reverse()

        for extension in self.extensions:
            on_end = yield extension.will_resolve_field(root, info, **args)
            yield on_end()

        @coroutine
        def on_end(error=None, result=None):
            raise Return((error, result))

        raise Return(on_end)

    @coroutine
    def will_send_response(self, response, context):
        ref = [response, context]
        ext = self.extensions[:]
        ext.reverse()

        for handler in ext:
            result = yield handler.will_send_response(ref[0], ref[1])
            if result:
                ref = [result, context]
        raise Return(ref)

    @coroutine
    def _handle_did_start(self, method, *args):
        end_handlers = []
        for extension in self.extensions:
            invoker = partial(getattr(extension, method), *args)
            end_handler = invoker()
            if end_handler:
                end_handlers.append(end_handler)

        @coroutine
        def end(errors=None):
            errors = errors or []
            end_handlers.reverse()
            for handler_future in end_handlers:
                handler = yield handler_future
                if handler:
                    yield handler(errors)

        raise Return(end)
