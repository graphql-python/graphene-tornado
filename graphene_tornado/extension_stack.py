"""
ExtensionStack is an adapter for GraphQLExtension that helps invoke a list of GraphQLExtension objects at runtime.
"""
import inspect
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
                 extensions: List[Union[Callable[[], GraphQLExtension], GraphQLExtension]] = None
                 ):
        self.extensions: List[GraphQLExtension] = list(instantiate_extensions(extensions))

    async def request_started(self, request, query_string, parsed_query, operation_name, variables, context, request_context):
        on_end = await self._handle_did_start('request_started', request, query_string, parsed_query, operation_name,
                                              variables, context, request_context)
        return on_end

    async def parsing_started(self, query_string):
        on_end = await self._handle_did_start('parsing_started', query_string)
        return on_end

    async def validation_started(self):
        on_end = await self._handle_did_start('validation_started')
        return on_end

    async def execution_started(self, schema, document, root, context, variables, operation_name, request_context):
        on_end = await self._handle_did_start('execution_started', schema, document, root, context,
                                              variables, operation_name, request_context)
        return on_end

    async def will_resolve_field(self, root, info, **args):
        ext = self.extensions[:]
        ext.reverse()

        for extension in self.extensions:
            on_end = await extension.will_resolve_field(root, info, **args)
            await on_end()

        async def on_end(error=None, result=None):
            return (error, result)

        return on_end

    async def will_send_response(self, response, context):
        ref = [response, context]
        ext = self.extensions[:]
        ext.reverse()

        for handler in ext:
            result = await handler.will_send_response(ref[0], ref[1])
            if result:
                ref = [result, context]
        return ref

    async def _handle_did_start(self, method, *args):
        end_handlers = []
        for extension in self.extensions:
            invoker = getattr(extension, method)
            end_handler = await invoker(*args)
            if end_handler:
                end_handlers.append(end_handler)

        async def end(errors=None):
            errors = errors or []
            end_handlers.reverse()
            for handler in end_handlers:
                if handler:
                    await handler(errors)

        return end
