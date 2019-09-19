from __future__ import absolute_import, print_function

import gzip
import logging
import os
import socket
import sys

import six
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import Message
from six import StringIO, BytesIO
from tornado.gen import coroutine
from tornado.httpclient import AsyncHTTPClient
from typing import NamedTuple, Optional, Callable

from tornado_retry_client import RetryClient

from graphene_tornado.apollo_tooling.operation_id import default_engine_reporting_signature
from .reports_pb2 import ReportHeader, FullTracesReport

LOGGER = logging.getLogger(__name__)

SERVICE_HEADER_DEFAULTS = {
  'hostname': socket.gethostname(),
  'agentVersion': 'apollo-engine-reporting@${require(\'../package.json\').version}',
  'runtimeVersion': 'python ' + '.'.join(map(str, sys.version_info[0:3])),
  'uname': ' '.join(os.uname()),
}

GenerateClientInfo = NamedTuple('GenerateClientInfo', [
    ('client_name', Optional[str]),
    ('client_version', Optional[str]),
    ('client_reference_id', Optional[str]),
])

EngineReportingOptions = NamedTuple('EngineReportingOptions', [
    ('api_key', Optional[str]),
    ('calculate_signature', Optional[Callable]),
    # ('report_interval_ms', Optional[int]),
    # ('max_uncompressed_report_size', Optional[int]),
    ('endpoint_url', Optional[str]),
    ('debug_print_reports', Optional[bool]),
    ('request_agent', Optional[bool]),
    # ('max_attempts', Optional[int]),
    # ('minimum_retry_delay_ms', Optional[int]),
    ('report_error_function', Optional[Callable]),
    # ('private_variables', Optional[List[str]]),
    # ('private_headers', Optional[List[str]]),
    # ('handle_signals', Optional[bool]),
    # ('send_reports_immediately', Optional[bool]),
    ('mask_errors_details', Optional[bool]),
    ('schema_tag', Optional[str]),
    ('generate_client_info', Optional[GenerateClientInfo])
])
EngineReportingOptions.__new__.__defaults__ = (None,) * len(EngineReportingOptions._fields)


def _serialize(message):
    # type: (Message) -> bytes
    out = BytesIO() if six.PY3 else StringIO()
    with gzip.GzipFile(fileobj=out, mode="w") as f:
        f.write(message.SerializeToString())
    return out.getvalue()


def _get_trace_signature(operation_name, document_ast, query_string):
    if not document_ast:
        return query_string
    else:
        return default_engine_reporting_signature(document_ast, operation_name)


class EngineReportingAgent:

    def __init__(self, options, schema_hash):  # type: (EngineReportingOptions, str) -> None
        self.options = options
        self.api_key = options.api_key or os.getenv('ENGINE_API_KEY', None)

        if not self.api_key:
            raise ValueError('To use EngineReportingAgent, you must specify an API key via the api_key option or the ' +
                             'ENGINE_API_KEY environment variable.')

        self.endpoint_url = self.options.endpoint_url or 'https://engine-report.apollodata.com/api/ingress/traces'
        self.request_headers = {
            'user-agent': 'apollo-engine-reporting',
            'x-api-key': self.api_key,
            'content-encoding': 'gzip',
        }

        self._stopped = False

        self.report_header = ReportHeader()
        self.report_header.hostname = SERVICE_HEADER_DEFAULTS['hostname']
        self.report_header.agent_version = SERVICE_HEADER_DEFAULTS['agentVersion']
        self.report_header.runtime_version = SERVICE_HEADER_DEFAULTS['runtimeVersion']
        self.report_header.uname = SERVICE_HEADER_DEFAULTS['uname']
        self.report_header.schema_hash = schema_hash
        self.report_header.schema_tag = options.schema_tag or os.getenv('ENGINE_SCHEMA_TAG', None) or ''

        self.report = FullTracesReport(header=self.report_header)
        self.report_size = 0

    def _options(self): # type: () -> EngineReportingOptions
        return self.options

    @coroutine
    def add_trace(self, operation_name, document_ast, query_string, trace):
        operation_name = operation_name or '-'

        if self._stopped:
            return

        signature = _get_trace_signature(operation_name, document_ast, query_string)
        stats_report_key = "# " + operation_name + '\n' + signature
        traces_per_query = self.report.traces_per_query.get(stats_report_key, None)
        if not traces_per_query:
            traces_per_query = self.report.traces_per_query[stats_report_key]
        traces_per_query.trace.extend([trace])

        yield self.send_report_and_report_errors()

    @coroutine
    def send_report(self):
        report = self.report
        self.reset_report()

        if len(report.traces_per_query) == 0:
            return

        if self.options.debug_print_reports:
            LOGGER.info('Engine sending report: ' + MessageToJson(report))

        yield self.post_data(_serialize(report))

    @coroutine
    def post_data(self, data):
        headers = {
            'Content-Length': len(data)
        }
        headers.update(self.request_headers)

        http_client = AsyncHTTPClient()
        retry_client = RetryClient(
            http_client=http_client,
            retry_attempts=3,
            retry_start_timeout=0.5,
            retry_max_timeout=10,
            retry_factor=2,
        )

        try:
            response = yield retry_client.fetch(self.endpoint_url, method='POST', headers=headers, body=data,
                                                raise_error=False)

        finally:
            http_client.close()

        if 500 <= response.code < 600:
            raise ValueError(response.code + ': ' + response.body)

        if response.code < 200 or response.code >= 300:
            raise ValueError('Error sending report to Engine servers (HTTP status {}): {}'
                             .format(response.code, response.body))

        if self.options.debug_print_reports:
            LOGGER.info('Engine report: status ' + response.code)

    def stop(self):
        self._stopped = True

    def send_report_and_report_errors(self):
        try:
            self.send_report()
        except:
            exception = sys.exc_info()[1]
            if self.options.report_error_function:
                self.options.report_error_function(exception)
            else:
                LOGGER.exception("Error sending reports to Apollo Engine")

    def reset_report(self):
        self.report = FullTracesReport(header=self.report_header)
        self.report_size = 0  # type: int


