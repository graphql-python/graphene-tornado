"""
GraphQLExtension is analogous to the server extensions that are provided
by Apollo Server: https://github.com/apollographql/apollo-server/tree/master/packages/graphql-extensions

Extensions are also middleware but have additional hooks.
"""
from __future__ import absolute_import, print_function

from abc import ABCMeta, abstractmethod
from typing import NewType, List, Callable, Optional, Dict, Any

from graphql import GraphQLSchema
from graphql.language.ast import Document
from tornado.httputil import HTTPServerRequest

EndHandler = NewType('EndHandler', Optional[List[Callable[[List[Exception]], None]]])


class GraphQLExtension:

    __metaclass__ = ABCMeta

    @abstractmethod
    def request_started(self,
                        request: HTTPServerRequest,
                        query_string: Optional[str],
                        parsed_query: Optional[Document],
                        operation_name: Optional[str],
                        variables: Optional[Dict[str, Any]],
                        context: Any,
                        request_context: Any
                        ) -> EndHandler:
        pass

    @abstractmethod
    def parsing_started(self, query_string: str) -> EndHandler:
        pass

    @abstractmethod
    def validation_started(self) -> EndHandler:
        pass

    @abstractmethod
    def execution_started(self,
                          schema: GraphQLSchema,
                          document: Document,
                          root: Any,
                          context: Optional[Any],
                          variables: Optional[Any],
                          operation_name: Optional[str],
                          request_context: Dict[Any, Any]
                          ) -> EndHandler:
        pass

    @abstractmethod
    def will_resolve_field(self, root, info, **args) -> EndHandler:
        pass

    @abstractmethod
    def will_send_response(self,
                           response: Any,
                           context: Any,
                           ) -> EndHandler:
        pass

    def as_middleware(self) -> Callable:
        """
        Adapter for using the stack as middleware so that the will_resolve_field function
        is invoked like normal middleware

        Returns:
            An adapter function that acts as middleware
        """
        async def middleware(next, root, info, **args):
            end_resolve = await self.will_resolve_field(root, info, **args)
            res = None
            errors = []
            try:
                res = next(root, info, **args)
                return res
            finally:
                await end_resolve(errors, res)
        return middleware
