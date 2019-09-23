from __future__ import absolute_import, print_function

import json
import sys
import time
from numbers import Number

from google.protobuf.timestamp_pb2 import Timestamp
from tornado.gen import coroutine, Return
from tornado.httputil import HTTPServerRequest
from typing import Callable, NamedTuple

from graphene_tornado.ext.apollo_engine_reporting.engine_agent import EngineReportingOptions
from graphene_tornado.ext.apollo_engine_reporting.reports_pb2 import Trace
from graphene_tornado.graphql_extension import GraphQLExtension

PY37 = sys.version_info[0:2] >= (3, 7)


CLIENT_NAME_HEADER = 'apollographql-client-name';
CLIENT_REFERENCE_HEADER_KEY = 'apollographql-client-reference-id';
CLIENT_VERSION_HEADER_KEY = 'apollographql-client-version';


ClientInfo = NamedTuple('EngineReportingOptions', [
    ('client_name', str),
    ('client_reference_id', str),
    ('client_version', str)
])


def generate_client_info(request):
    # type: (HTTPServerRequest) -> ClientInfo
    return ClientInfo(
        request.headers.get(CLIENT_NAME_HEADER, ''),
        request.headers.get(CLIENT_REFERENCE_HEADER_KEY, ''),
        request.headers.get(CLIENT_VERSION_HEADER_KEY, ''),
    )


def response_path_as_string(path):
    if not path:
        return ''
    return '.'.join((str(x) for x in path))


def now_ns():
    if PY37:
        return time.time_ns()

    return long(time.time() * 1000000000)


class EngineReportingExtension(GraphQLExtension):

    def __init__(self, options, add_trace):  # type: (EngineReportingOptions, Callable) -> None
        if add_trace is None:
            raise ValueError('add_trace must be defined')

        self.add_trace = add_trace
        self.operation_name = None

        self.options = options  # maskErrorDetails = False
        self.start_time = now_ns()

        root = Trace.Node()
        root.start_time = self.start_time
        self.trace = Trace(root=root)
        self.nodes = {response_path_as_string(None): root}
        self.generate_client_info = options.generate_client_info or generate_client_info
        self.resolver_stats = list()

    @coroutine
    def request_started(self, request, query_string, parsed_query, operation_name, variables, context, request_context):
        self.trace.start_time.GetCurrentTime()
        self.query_string = query_string
        self.document = parsed_query
        self.trace.http.method = self._get_http_method(request)

        client_info = generate_client_info(request)
        if client_info:
            self.trace.client_version = client_info.client_version or ''
            self.trace.client_reference_id = client_info.client_reference_id or ''
            self.trace.client_name = client_info.client_name or ''

        @coroutine
        def on_request_ended(errors):
            start_nanos = self.trace.start_time.ToNanoseconds()
            now = Timestamp()
            now.GetCurrentTime()
            self.trace.duration_ns = now.ToNanoseconds() - start_nanos
            self.trace.end_time.GetCurrentTime()

            op_name = self.operation_name or ''
            self.trace.root.MergeFrom(self.nodes.get(''))
            yield self.add_trace(op_name, self.document.document_ast, self.query_string, self.trace)

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

        node = self._new_node(info.path)
        node.start_time = now_ns() - self.start_time
        node.type = str(info.return_type)
        node.parent_type = str(info.parent_type)

        @coroutine
        def on_end(errors=None, result=None):
            node.end_time = now_ns() - self.start_time

        raise Return(on_end)

    @coroutine
    def will_send_response(self, response, context):
        root = self.nodes.get('', None)
        root.end_time = now_ns()

        if hasattr(response, 'errors'):
            errors = response.errors
            for error in errors:
                node = root
                if hasattr(error, 'path'):
                    specific_node = self.nodes.get(error.path.join('.'))
                    if specific_node:
                        node = specific_node

                if hasattr(self.options, 'mask_error_details') and self.options.mask_errors_details:
                    error_info = {
                        'message': '<masked>'
                    }
                else:
                    error_info = {
                        'message': str(error),
                        'json': json.dumps(error)
                    }
                node.error.add(error=Trace.Error(**error_info))

    def _get_http_method(self, request):
        try:
            return getattr(Trace.HTTP, request.method.upper())
        except:
            return Trace.HTTP.UNKNOWN

    def _new_node(self, path):
        node = Trace.Node()

        id = path[-1]
        if isinstance(id, Number):
            node.index = id
        else:
            node.response_name = id

        self.nodes[response_path_as_string(path)] = node
        parent_node = self._ensure_parent_node(path)
        n = parent_node.child.add()
        n.MergeFrom(node)
        self.nodes[response_path_as_string(path)] = n
        return n

    def _ensure_parent_node(self, path):
        prev = [''] if len(path) == 1 else path[:-1]
        parent_path = response_path_as_string(prev)
        parent_node = self.nodes.get(parent_path, None)
        if parent_node:
            return parent_node
        return self._new_node(prev)

