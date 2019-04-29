from __future__ import absolute_import, division, print_function

import inspect
import json
import sys
import traceback

import six
from graphene_tornado.render_graphiql import render_graphiql
from graphene_tornado.tornado_executor import TornadoExecutor
from graphql import get_default_backend, execute, validate
from graphql.error import GraphQLError
from graphql.error import format_error as format_graphql_error
from graphql.execution import ExecutionResult
from tornado import web
from tornado.escape import json_encode, to_unicode
from tornado.gen import coroutine, Return
from tornado.locks import Event
from tornado.log import app_log
from tornado.web import HTTPError
from werkzeug.datastructures import MIMEAccept
from werkzeug.http import parse_accept_header


class ExecutionError(Exception):
    def __init__(self, status_code=400, errors=None):
        self.status_code = status_code
        if errors is None:
            self.errors = []
        else:
            self.errors = [str(e) for e in errors]
        self.message = '\n'.join(self.errors)


class TornadoGraphQLHandler(web.RequestHandler):

    executor = None
    schema = None
    batch = False
    middleware = []
    pretty = False
    root_value = None
    graphiql = False
    graphiql_version = None
    graphiql_template = None
    graphiql_html_title = None
    backend = None
    document = None
    graphql_params = None
    parsed_body = None

    def initialize(self, schema=None, executor=None, middleware=None, root_value=None, graphiql=False, pretty=False,
                   batch=False, backend=None):
        super(TornadoGraphQLHandler, self).initialize()

        self.schema = schema
        if middleware is not None:
            self.middleware = list(self.instantiate_middleware(middleware))
        self.executor = executor
        self.root_value = root_value
        self.pretty = pretty
        self.graphiql = graphiql
        self.batch = batch
        self.backend = backend or get_default_backend()

    @property
    def context(self):
        return self.request

    def get_root(self):
        return self.root_value

    def get_middleware(self):
        return self.middleware

    def get_backend(self):
        return self.backend

    def get_document(self):
        return self.document

    def get_parsed_body(self):
        return self.parsed_body

    @coroutine
    def get(self):
        try:
            yield self.run('get')
        except Exception as ex:
            self.handle_error(ex)

    @coroutine
    def post(self):
        try:
            yield self.run('post')
        except Exception as ex:
            self.handle_error(ex)

    @coroutine
    def run(self, method):
        show_graphiql = self.graphiql and self.should_display_graphiql()
        data = self.parse_body()

        if self.batch:
            responses = []
            for entry in data:
                r = yield self.get_response(entry, method, entry)
                responses.append(r)
            result = '[{}]'.format(','.join([response[0] for response in responses]))
            status_code = max(responses, key=lambda response: response[1])[1]
        else:
            result, status_code = yield self.get_response(data, method, show_graphiql)

        if show_graphiql:
            query, variables, operation_name, id = self.get_graphql_params(self.request, data)
            graphiql = self.render_graphiql(
                query=query or '',
                variables='' if variables is None else json.dumps(variables),
                operation_name=operation_name or '',
                result=result or ''
            )
            self.write(graphiql)
            self.finish()
            return

        self.set_status(status_code)
        self.set_header('Content-Type', 'application/json')
        self.write(result)
        self.finish()

    def parse_body(self):
        content_type = self.content_type

        if content_type == 'application/graphql':
            self.parsed_body = {'query': to_unicode(self.request.body)}
            return self.parsed_body
        elif content_type == 'application/json':
            # noinspection PyBroadException
            try:
                body = self.request.body
            except Exception as e:
                raise ExecutionError(400, e)

            try:
                request_json = json.loads(to_unicode(body))
                if self.batch:
                    assert isinstance(request_json, list), (
                        'Batch requests should receive a list, but received {}.'
                    ).format(repr(request_json))
                    assert len(request_json) > 0, (
                        'Received an empty list in the batch request.'
                    )
                else:
                    assert isinstance(request_json, dict), (
                        'The received data is not a valid JSON query.'
                    )
                self.parsed_body = request_json
                return self.parsed_body
            except AssertionError as e:
                raise HTTPError(status_code=400, log_message=str(e))
            except (TypeError, ValueError):
                raise HTTPError(status_code=400, log_message='POST body sent invalid JSON.')

        elif content_type in ['application/x-www-form-urlencoded', 'multipart/form-data']:
            self.parsed_body = self.request.query_arguments
            return self.parsed_body

        self.parsed_body = {}
        return self.parsed_body

    @coroutine
    def get_response(self, data, method, show_graphiql=False):
        query, variables, operation_name, id = self.get_graphql_params(self.request, data)

        execution_result = yield self.execute_graphql_request(
            method,
            query,
            variables,
            operation_name,
            show_graphiql
        )

        status_code = 200
        if execution_result:
            response = {}

            if getattr(execution_result, 'is_pending', False):
                event = Event()
                on_resolve = lambda *_: event.set()  # noqa
                execution_result.then(on_resolve).catch(on_resolve)
                yield event.wait()

            if hasattr(execution_result, 'get'):
                execution_result = execution_result.get()

            if execution_result.errors:
                response['errors'] = [self.format_error(e) for e in execution_result.errors]

            if execution_result.invalid:
                status_code = 400
            else:
                response['data'] = execution_result.data

            if self.batch:
                response['id'] = id
                response['status'] = status_code

            result = self.json_encode(response, pretty=self.pretty or show_graphiql)
        else:
            result = None

        raise Return((result, status_code))

    @coroutine
    def execute_graphql_request(self, method, query, variables, operation_name, show_graphiql=False):
        if not query:
            if show_graphiql:
                raise Return(None)
            raise HTTPError(400, 'Must provide query string.')

        if not self.document:
            try:
                backend = self.get_backend()
                self.document = backend.document_from_string(self.schema, query)
            except Exception as e:
                raise Return(ExecutionResult(errors=[e], invalid=True))

        try:
            validation_errors = validate(self.schema, self.document.document_ast)
        except Exception as e:
            raise Return(ExecutionResult(errors=[e], invalid=True))

        if validation_errors:
            raise Return(ExecutionResult(
                errors=validation_errors,
                invalid=True,
            ))

        if method.lower() == 'get':
            operation_type = self.document.get_operation_type(operation_name)
            if operation_type and operation_type != "query":
                if show_graphiql:
                    raise Return(None)

                raise HTTPError(405, 'Can only perform a {} operation from a POST request.'
                                .format(operation_type))

        try:
            result = yield self.execute(
                self.document.document_ast,
                root=self.get_root(),
                variables=variables,
                operation_name=operation_name,
                context=self.context,
                middleware=self.get_middleware(),
                executor=self.executor or TornadoExecutor(),
                return_promise=True
            )
        except Exception as e:
            raise Return(ExecutionResult(errors=[e], invalid=True))

        raise Return(result)

    @coroutine
    def execute(self, *args, **kwargs):
        raise Return(execute(self.schema, *args, **kwargs))

    def json_encode(self, d, pretty=False):
        if pretty or self.get_query_argument('pretty', False):
            return json.dumps(d, sort_keys=True, indent=2, separators=(',', ': '))

        return json.dumps(d, separators=(',', ':'))

    def render_graphiql(self, query, variables, operation_name, result):
        return render_graphiql(
            query=query,
            variables=variables,
            operation_name=operation_name,
            result=result,
            graphiql_version=self.graphiql_version,
            graphiql_template=self.graphiql_template,
            graphiql_html_title=self.graphiql_html_title,
        )

    def should_display_graphiql(self):
        raw = 'raw' in self.request.query_arguments.keys() or 'raw' in self.request.arguments
        return not raw and self.request_wants_html()

    def request_wants_html(self):
        accept_header = self.request.headers.get('Accept', '')
        accept_mimetypes = parse_accept_header(accept_header, MIMEAccept)
        best = accept_mimetypes.best_match(['application/json', 'text/html'])
        return best == 'text/html' and accept_mimetypes[best] > accept_mimetypes['application/json']

    @property
    def content_type(self):
        return self.request.headers.get('Content-Type', 'text/plain').split(';')[0]

    @staticmethod
    def instantiate_middleware(middlewares):
        for middleware in middlewares:
            if inspect.isclass(middleware):
                yield middleware()
                continue
            yield middleware

    def get_graphql_params(self, request, data):
        if self.graphql_params:
            return self.graphql_params

        single_args = {}
        for key in request.arguments.keys():
            single_args[key] = self.decode_argument(request.arguments.get(key)[0])

        query = single_args.get('query') or data.get('query')
        variables = single_args.get('variables') or data.get('variables')
        id = single_args.get('id') or data.get('id')

        if variables and isinstance(variables, six.string_types):
            try:
                variables = json.loads(variables)
            except:  # noqa
                raise HTTPError(400, 'Variables are invalid JSON.')

        operation_name = single_args.get('operationName') or data.get('operationName')
        if operation_name == "null":
            operation_name = None

        self.graphql_params = query, variables, operation_name, id
        return self.graphql_params

    def handle_error(self, ex):
        if not isinstance(ex, (web.HTTPError, ExecutionError, GraphQLError)):
            tb = ''.join(traceback.format_exception(*sys.exc_info()))
            app_log.error('Error: {0} {1}'.format(ex, tb))
        self.set_status(self.error_status(ex))
        error_json = json_encode({'errors': self.error_format(ex)})
        app_log.debug('error_json: %s', error_json)
        self.write(error_json)

    @staticmethod
    def error_status(exception):
        if isinstance(exception, web.HTTPError):
            return exception.status_code
        elif isinstance(exception, (ExecutionError, GraphQLError)):
            return 400
        else:
            return 500

    @staticmethod
    def error_format(exception):
        if isinstance(exception, ExecutionError):
            return [{'message': e} for e in exception.errors]
        elif isinstance(exception, GraphQLError):
            return [format_graphql_error(exception)]
        elif isinstance(exception, web.HTTPError):
            return [{'message': exception.log_message}]
        else:
            return [{'message': 'Unknown server error'}]

    @staticmethod
    def format_error(error):
        if isinstance(error, GraphQLError):
            return format_graphql_error(error)

        return {'message': six.text_type(error)}
