"""
GraphQLExtension is analogous to the server extensions that are provided
by Apollo Server: https://github.com/apollographql/apollo-server/tree/master/packages/graphql-extensions

Extensions are also middleware but have additional hooks.
"""
from __future__ import absolute_import, print_function

from abc import ABCMeta, abstractmethod

from tornado.gen import coroutine, Return
from typing import NewType, List, Callable, Optional

EndHandler = NewType('EndHandler', Optional[List[Callable[[List[Exception]], None]]])


class GraphQLExtension:

    __metaclass__ = ABCMeta

    @abstractmethod
    def request_started(self,
                        request,         # type: HTTPServerRequest
                        query_string,    # type: Optional[str],
                        parsed_query,    # type: Optional[Document]
                        operation_name,  # type: Optional[str]
                        variables,       # type: Optional[dict[str, Any]]
                        context,         # type: Any
                        request_context  # type: Any
                        ):
        # type: (...) -> EndHandler
        pass

    @abstractmethod
    def parsing_started(self, query_string):  # type: (str) -> EndHandler
        pass

    @abstractmethod
    def validation_started(self):
        # type: () -> EndHandler
        pass

    @abstractmethod
    def execution_started(self,
                          schema,  # type: GraphQLSchema
                          document,  # type: Document
                          root,  # type: Any
                          context,  # type: Optional[Any]
                          variables,  # type: Optional[Any]
                          operation_name  # type: Optional[str]
                          ):
        # type: (...) -> EndHandler
        pass

    @abstractmethod
    def will_resolve_field(self, root, info, **args):
        # type: (...) -> EndHandler
        pass

    @abstractmethod
    def will_send_response(self,
                           response,  # type: Any
                           context,   # type: Any
                           ):
        # type: (...) -> EndHandler
        pass

    def as_middleware(self):
        # type: () -> Callable
        """
        Adapter for using the stack as middleware so that the will_resolve_field function
        is invoked like normal middleware

        Returns:
            An adapter function that acts as middleware
        """
        @coroutine
        def middleware(next, root, info, **args):
            end_resolve = yield self.will_resolve_field(root, info, **args)
            res = None
            errors = []
            try:
                res = next(root, info, **args)
                raise Return(res)
            finally:
                yield end_resolve(errors, res)
        return middleware
