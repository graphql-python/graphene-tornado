import inspect
import json
import sys
import traceback
from asyncio import iscoroutinefunction
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from graphene.types.schema import Schema
from graphql import DocumentNode
from graphql import execute
from graphql import get_operation_ast
from graphql import OperationType
from graphql import parse
from graphql import validate
from graphql.error import GraphQLFormattedError  as format_graphql_error
from graphql.error.graphql_error import GraphQLError
from graphql.error.syntax_error import GraphQLSyntaxError
from graphql.execution.execute import ExecutionResult
from graphql.pyutils import is_awaitable
from tornado import web
from tornado.escape import json_encode
from tornado.escape import to_unicode
from tornado.httputil import HTTPServerRequest
from tornado.log import app_log
from tornado.web import HTTPError
from typing_extensions import Awaitable
from werkzeug.datastructures import MIMEAccept
from werkzeug.http import parse_accept_header

from graphene_tornado.extension_stack import GraphQLExtensionStack
from graphene_tornado.graphql_extension import GraphQLExtension
from graphene_tornado.render_graphiql import render_graphiql


class ExecutionError(Exception):
    def __init__(self, status_code=400, errors=None):
        self.status_code = status_code
        if errors is None:
            self.errors = []
        else:
            self.errors = [str(e) for e in errors]
        self.message = "\n".join(self.errors)


class TornadoGraphQLHandler(web.RequestHandler):

    schema: Schema
    batch: bool = False
    middleware: List[Any] = []
    pretty: bool = False
    root_value: Optional[Any] = None
    graphiql: bool = False
    graphiql_version: Optional[str] = None
    graphiql_template: Optional[str] = None
    graphiql_html_title: Optional[str] = None
    document: Optional[DocumentNode]
    graphql_params: Optional[Tuple[Any, Any, Any, Any]] = None
    parsed_body: Optional[Dict[str, Any]] = None
    extension_stack = GraphQLExtensionStack([])
    request_context: Dict[str, Any] = {}

    def initialize(
        self,
        schema: Optional[Schema] = None,
        middleware: Optional[Any] = None,
        root_value: Any = None,
        graphiql: bool = False,
        pretty: bool = False,
        batch: bool = False,
        extensions: List[
            Union[Callable[[], GraphQLExtension], GraphQLExtension]
        ] = None,
    ) -> None:
        super(TornadoGraphQLHandler, self).initialize()

        self.schema = schema

        middlewares = []
        if extensions:
            self.extension_stack = GraphQLExtensionStack(extensions)
            middlewares.extend([self.extension_stack.as_middleware()])

        if middleware is not None:
            middlewares.extend(list(self.instantiate_middleware(middleware)))

        if len(middlewares) > 0:
            self.middleware = middlewares

        self.root_value = root_value
        self.pretty = pretty
        self.graphiql = graphiql
        self.batch = batch

    @property
    def context(self) -> HTTPServerRequest:
        return self.request

    def get_root(self) -> Any:
        return self.root_value

    def get_middleware(self) -> List[Callable]:
        return self.middleware

    def get_document(self) -> Optional[DocumentNode]:
        return self.document

    def get_parsed_body(self):
        return self.parsed_body

    async def get(self) -> None:
        try:
            await self.run("get")
        except Exception as ex:
            self.handle_error(ex)

    async def post(self) -> None:
        try:
            await self.run("post")
        except Exception as ex:
            self.handle_error(ex)

    async def run(self, method: str) -> None:
        show_graphiql = self.graphiql and self.should_display_graphiql()

        if show_graphiql:
            # We want to disable extensions when serving GraphiQL
            self.extension_stack.extensions = []

        data = self.parse_body()

        if self.batch:
            responses = []
            for entry in data:
                r = await self.get_response(entry, method, entry)
                responses.append(r)
            result = "[{}]".format(",".join([response[0] for response in responses]))
            status_code = max(responses, key=lambda response: response[1])[1]
        else:
            result, status_code = await self.get_response(data, method, show_graphiql)

        if show_graphiql:
            query, variables, operation_name, id = self.get_graphql_params(
                self.request, data
            )
            graphiql = self.render_graphiql(
                query=query or "",
                variables="" if variables is None else json.dumps(variables),
                operation_name=operation_name or "",
                result=result or "",
            )
            self.write(graphiql)
            await self.finish()
            return

        self.set_status(status_code)
        self.set_header("Content-Type", "application/json")
        self.write(result)
        await self.finish()

    def parse_body(self) -> Any:
        content_type = self.content_type

        if content_type == "application/graphql":
            self.parsed_body = {"query": to_unicode(self.request.body)}
            return self.parsed_body
        elif content_type == "application/json":
            # noinspection PyBroadException
            try:
                body = self.request.body
            except Exception as e:
                raise ExecutionError(400, e)

            try:
                request_json = json.loads(to_unicode(body))
                if self.batch:
                    assert isinstance(request_json, list), (
                        "Batch requests should receive a list, but received {}."
                    ).format(repr(request_json))
                    assert (
                        len(request_json) > 0
                    ), "Received an empty list in the batch request."
                else:
                    assert isinstance(
                        request_json, dict
                    ), "The received data is not a valid JSON query."
                self.parsed_body = request_json
                return self.parsed_body
            except AssertionError as e:
                raise HTTPError(status_code=400, log_message=str(e))
            except (TypeError, ValueError):
                raise HTTPError(
                    status_code=400, log_message="POST body sent invalid JSON."
                )

        elif content_type in [
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        ]:
            self.parsed_body = self.request.query_arguments
            return self.parsed_body

        self.parsed_body = {}
        return self.parsed_body

    async def get_response(self, data, method, show_graphiql=False):
        query, variables, operation_name, id = self.get_graphql_params(
            self.request, data
        )

        request_end = await self.extension_stack.request_started(
            self.request,
            query,
            None,
            operation_name,
            variables,
            self.context,
            self.request_context,
        )

        try:
            execution_result, invalid = await self.execute_graphql_request(
                method, query, variables, operation_name, show_graphiql
            )

            status_code = 200
            if execution_result:
                response = {}

                if is_awaitable(execution_result) or iscoroutinefunction(
                    execution_result
                ):
                    execution_result = await execution_result

                if hasattr(execution_result, "get"):
                    execution_result = execution_result.get()

                if execution_result.errors:
                    response["errors"] = [
                        self.format_error(e) for e in execution_result.errors
                    ]

                if invalid:
                    status_code = 400
                else:
                    response["data"] = execution_result.data

                if self.batch:
                    response["id"] = id
                    response["status"] = status_code

                result = self.json_encode(response, pretty=self.pretty or show_graphiql)
            else:
                result = None

            res = (result, status_code)
            await self.extension_stack.will_send_response(result, self.context)
            return res
        finally:
            await request_end()

    async def execute_graphql_request(
        self,
        method: str,
        query: Optional[str],
        variables: Optional[Dict[str, str]],
        operation_name: Optional[str],
        show_graphiql: bool = False,
    ) -> Tuple[
        Optional[Union[Awaitable[ExecutionResult], ExecutionResult]], Optional[bool]
    ]:
        if not query:
            if show_graphiql:
                return None, None
            raise HTTPError(400, "Must provide query string.")

        parsing_ended = await self.extension_stack.parsing_started(query)
        try:
            self.document = parse(query)
            await parsing_ended()
        except GraphQLError as e:
            await parsing_ended(e)
            return ExecutionResult(errors=[e], data=None), True

        validation_ended = await self.extension_stack.validation_started()
        try:
            validation_errors = validate(self.schema.graphql_schema, self.document)
        except GraphQLError as e:
            await validation_ended([e])
            return ExecutionResult(errors=[e], data=None), True

        if validation_errors:
            await validation_ended(validation_errors)
            return ExecutionResult(errors=validation_errors, data=None,), True
        else:
            await validation_ended()

        if method.lower() == "get":
            operation_node = get_operation_ast(self.document, operation_name)
            if not operation_node:
                if show_graphiql:
                    return None, None
                raise HTTPError(
                    405,
                    "Must provide operation name if query contains multiple operations.",
                )

            if not operation_node.operation == OperationType.QUERY:
                if show_graphiql:
                    return None, None
                raise HTTPError(
                    405,
                    "Can only perform a {} operation from a POST request.".format(
                        operation_node.operation.value
                    ),
                )

        execution_ended = await self.extension_stack.execution_started(
            schema=self.schema.graphql_schema,
            document=self.document,
            root=self.root_value,
            context=self.context,
            variables=variables,
            operation_name=operation_name,
            request_context=self.request_context,
        )
        try:
            result = await self.execute(
                self.document,
                root_value=self.get_root(),
                variable_values=variables,
                operation_name=operation_name,
                context_value=self.context,
                middleware=self.get_middleware(),
            )
            await execution_ended()
        except GraphQLError as e:
            await execution_ended([e])
            return ExecutionResult(errors=[e], data=None), True

        return result, False

    async def execute(
        self, *args, **kwargs
    ) -> Union[Awaitable[ExecutionResult], ExecutionResult]:
        return execute(self.schema.graphql_schema, *args, **kwargs)

    def json_encode(self, d: Dict[str, Any], pretty: bool = False) -> str:
        if pretty or self.get_query_argument("pretty", False):  # type: ignore
            return json.dumps(d, sort_keys=True, indent=2, separators=(",", ": "))

        return json.dumps(d, separators=(",", ":"))

    def render_graphiql(
        self, query: str, variables: str, operation_name: str, result: str
    ) -> str:
        return render_graphiql(
            query=query,
            variables=variables,
            operation_name=operation_name,
            result=result,
            graphiql_version=self.graphiql_version,
            graphiql_template=self.graphiql_template,
            graphiql_html_title=self.graphiql_html_title,
        )

    def should_display_graphiql(self) -> bool:
        raw = (
            "raw" in self.request.query_arguments.keys()
            or "raw" in self.request.arguments
        )
        return not raw and self.request_wants_html()

    def request_wants_html(self) -> bool:
        accept_header = self.request.headers.get("Accept", "")
        accept_mimetypes = parse_accept_header(accept_header, MIMEAccept)
        best = accept_mimetypes.best_match(["application/json", "text/html"])
        return (
            best == "text/html"
            and accept_mimetypes[best] > accept_mimetypes["application/json"]
        )

    @property
    def content_type(self) -> str:
        return self.request.headers.get("Content-Type", "text/plain").split(";")[0]

    @staticmethod
    def instantiate_middleware(middlewares):
        for middleware in middlewares:
            if inspect.isclass(middleware):
                yield middleware()
                continue
            yield middleware

    def get_graphql_params(
        self, request: HTTPServerRequest, data: Dict[str, Any]
    ) -> Any:
        if self.graphql_params:
            return self.graphql_params

        single_args = {}
        for key in request.arguments.keys():
            single_args[key] = self.decode_argument(request.arguments.get(key)[0])  # type: ignore

        query = single_args.get("query") or data.get("query")
        variables = single_args.get("variables") or data.get("variables")
        id = single_args.get("id") or data.get("id")

        if variables and isinstance(variables, str):
            try:
                variables = json.loads(variables)
            except:  # noqa
                raise HTTPError(400, "Variables are invalid JSON.")

        operation_name = single_args.get("operationName") or data.get("operationName")
        if operation_name == "null":
            operation_name = None

        self.graphql_params = query, variables, operation_name, id
        return self.graphql_params

    def handle_error(self, ex: Exception) -> None:
        if not isinstance(ex, (web.HTTPError, ExecutionError, GraphQLError)):
            tb = "".join(traceback.format_exception(*sys.exc_info()))
            app_log.error("Error: {0} {1}".format(ex, tb))
        self.set_status(self.error_status(ex))
        error_json = json_encode({"errors": self.error_format(ex)})
        app_log.debug("error_json: %s", error_json)
        self.write(error_json)

    @staticmethod
    def error_status(exception: Exception) -> int:
        if isinstance(exception, web.HTTPError):
            return exception.status_code
        elif isinstance(exception, (ExecutionError, GraphQLError)):
            return 400
        else:
            return 500

    @staticmethod
    def error_format(exception: Exception) -> List[Dict[str, Any]]:
        if isinstance(exception, ExecutionError):
            return [{"message": e} for e in exception.errors]
        elif isinstance(exception, GraphQLError):
            return [format_graphql_error(exception)]
        elif isinstance(exception, web.HTTPError):
            return [{"message": exception.log_message}]
        else:
            return [{"message": "Unknown server error"}]

    @staticmethod
    def format_error(error: Union[GraphQLError, GraphQLSyntaxError]) -> Dict[str, Any]:
        if isinstance(error, GraphQLError):
            return format_graphql_error(error)

        return {"message": str(error)}
