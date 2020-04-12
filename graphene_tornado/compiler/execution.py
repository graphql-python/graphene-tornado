import json
from dataclasses import dataclass
from typing import Any, Optional, List, Callable, Dict

from graphql import (
    GraphQLObjectType,
    GraphQLError,
    GraphQLSchema,
    TypeNameMetaFieldDef,
)
from graphql.execution.utils import (
    ExecutionContext as GraphQLContext,
    get_operation_root_type,
    collect_fields,
)
from graphql.language.ast import (
    OperationDefinition,
    FragmentDefinition,
    Document,
    Field,
)
from graphql.pyutils.default_ordered_dict import DefaultOrderedDict

from graphene_tornado.compiler.json import query_to_json_schema, fast_json
from graphene_tornado.compiler.path import Path
from graphene_tornado.compiler.variables import compile_variable_parsing

SAFETY_CHECK_PREFIX = "__validNode"
GLOBAL_DATA_NAME = "__context.data"
GLOBAL_ERRORS_NAME = "__context.errors"
GLOBAL_NULL_ERRORS_NAME = "__context.nullErrors"
GLOBAL_ROOT_NAME = "__context.rootValue"
GLOBAL_VARIABLES_NAME = "__context.variables"
GLOBAL_CONTEXT_NAME = "__context.context"
GLOBAL_EXECUTION_CONTEXT = "__context"
GLOBAL_PROMISE_COUNTER = "__context.promiseCounter"
GLOBAL_INSPECT_NAME = "__context.inspect"
GLOBAL_SAFE_MAP_NAME = "__context.safeMap"
GRAPHQL_ERROR = "__context.GraphQLError"
GLOBAL_RESOLVE = "__context.resolve"
GLOBAL_PARENT_NAME = "__parent"


@dataclass
class CompilerOptions(object):
    custom_json_serializer: bool = False
    disable_leaf_serialization: bool = False
    disable_capturing_stack_errors: bool = False
    custom_serializers: Dict[str, Any] = None
    resolver_info_enricher: Optional[Callable] = None


@dataclass
class DeferredField:
    name: str
    responsePath: Path
    originPaths: List[str]
    destinationPaths: List[str]
    parentType: GraphQLObjectType
    fieldName: str
    fieldType: Any
    fieldNodes: List[Any]
    args: Any


class CompilationContext(GraphQLContext):
    resolvers: Dict[str, Any]
    hoistedFunctions: List[str]
    hoistedFunctionNames: Dict[str, int]
    typeResolvers: Any
    isTypeOfs: Any
    resolveInfos: Dict[str, Any]
    deferred: List[DeferredField]
    options: CompilerOptions
    depth: int
    operation: OperationDefinition

    def __init__(
        self,
        schema=None,
        document_ast=None,
        root_value=None,
        context_value=None,
        variable_values=None,
        operation_name=None,
        executor=None,
        middleware=None,
        allow_subscriptions=None,
        fragments=None,
        resolvers=None,
        hoistedFunctions=None,
        hostedFunctionNames=None,
        typeResolvers=None,
        isTypeOfs=None,
        resolveInfos=None,
        deferred=None,
        options=None,
        depth=None,
        operation=None,
        serializers=None,
    ):
        # super().__init__(schema, document_ast, root_value, context_value, variable_values, operation_name, executor,
        #                 middleware, allow_subscriptions)
        self.resolvers = resolvers
        self.hoistedFunctions = hoistedFunctions
        self.hoistedFunctionNames = hostedFunctionNames
        self.typeResolvers = typeResolvers
        self.isTypeOfs = isTypeOfs
        self.resolveInfos = resolveInfos
        self.deferred = deferred
        self.options = options
        self.depth = depth
        self.fragments = fragments
        self.operation = operation
        self.serializers = serializers


class ExecutionContext:
    promiseCounter: int
    data: Any
    errors: Any
    nullErrors: Any
    resolve: Optional[Callable]
    inspect: Any
    variables: Any
    context: Any
    rootValue: Any
    safeMap: Any
    GraphQLError: Any
    resolvers: Any
    trimmer: Any
    serializers: Any
    typeResolvers: Any
    isTypeOfs: Any
    resolveInfos: Any


class CompiledQuery:
    operationName: Optional[str]
    query: Any
    stringify: Any


class ObjectPath:
    pass
#  prev: ObjectPath | undefined;
#  key: string;
#  type: ResponsePathType;
#  }


def compile_query(
    schema: GraphQLSchema,
    document: Document,
    operation_name: Optional[str] = None,
    options: Optional[str] = None,
) -> CompiledQuery:
    if not options:
        options = CompilerOptions()

    if not schema:
        raise ValueError("schema")

    if not document:
        raise ValueError("document")

    context = build_compilation_context(schema, document, options, operation_name)

    if options.custom_json_serializer:
        json_schema = query_to_json_schema(context)
        stringify = fast_json(json_schema)
    else:
        stringify = json.dumps

    get_variables = compile_variable_parsing(
        schema, context.operation.variable_definitions or []
    )

    function_body = compile_operation(context)
    compiled_query = {
        "query": create_bound_query(
            context,
            document,
            None,
            get_variables,
            context.operation.name.value if context.operation.name else None,
        )
    }

    return compiled_query


def build_compilation_context(
    schema, document: Document, options, operation_name
) -> CompilationContext:
    errors = []
    operation = None
    has_multiple_assumed_operations = []
    fragments = {}
    for definition in document.definitions:
        if isinstance(definition, OperationDefinition):
            if operation_name and operation:
                has_multiple_assumed_operations = True
            elif not operation_name or (
                definition.name and definition.name.value == operation_name
            ):
                operation = definition
        elif isinstance(definition, FragmentDefinition):
            fragments[definition.name.value] = definition

    if not operation:
        if operation_name:
            raise GraphQLError(f'Unknown operation named "{operation_name}".')
        else:
            raise GraphQLError("Must provide dan operation")

    return CompilationContext(
        schema=schema,
        fragments=fragments,
        root_value=None,
        context_value=None,
        operation=operation,
        resolvers={},
        serializers={},
        typeResolvers={},
        isTypeOfs={},
        resolveInfos={},
    )


def compile_operation(context: CompilationContext) -> str:
    type = get_operation_root_type(context.schema, context.operation)
    serial_execution = context.operation.operation == "mutation"
    field_map = collect_fields(
        context, type, context.operation.selection_set, DefaultOrderedDict(), set(),
    )
    top_level = compile_object_type(
        context,
        type,
        [],
        [GLOBAL_ROOT_NAME],
        [GLOBAL_ROOT_NAME],
        None,
        GLOBAL_ERRORS_NAME,
        field_map,
        True,
    )
    body = """
function query (${GLOBAL_EXECUTION_CONTEXT}) {
  "use strict";
"""
    if serial_execution:
        body += f"${GLOBAL_EXECUTION_CONTEXT}.queue = [];"
    body += generate_unique_declarations(context, True)
    body += f"{GLOBAL_DATA_NAME} = {top_level}\n"
    if serial_execution:
        body += compile_deferred_fields_serially(context)
        body += """
  ${GLOBAL_EXECUTION_CONTEXT}.finalResolve = () => {};
  ${GLOBAL_RESOLVE} = (context) => {
    if (context.jobCounter >= context.queue.length) {
      // All mutations have finished
      context.finalResolve(context);
      return;
    }
    context.queue[context.jobCounter++](context);
  };
  // There might not be a job to run due to invalid queries
  if (${GLOBAL_EXECUTION_CONTEXT}.queue.length > 0) {
    ${GLOBAL_EXECUTION_CONTEXT}.jobCounter = 1; // since the first one will be run manually
    ${GLOBAL_EXECUTION_CONTEXT}.queue[0](${GLOBAL_EXECUTION_CONTEXT});
  }
  // Promises have been scheduled so a new promise is returned
  // that will be resolved once every promise is done
  if (${GLOBAL_PROMISE_COUNTER} > 0) {
    return new Promise(resolve => ${GLOBAL_EXECUTION_CONTEXT}.finalResolve = resolve);
  }
"""
    else:
        body += compile_deferred_fields(context)
        body += """
          // Promises have been scheduled so a new promise is returned
          // that will be resolved once every promise is done
          if (${GLOBAL_PROMISE_COUNTER} > 0) {
            return new Promise(resolve => ${GLOBAL_RESOLVE} = resolve);
          """
        body += """
        // sync execution, the results are ready
        return undefined;
    """
    body += context.hoistedFunctions.join("\n")
    return body


def add_path(response_path, name):
    pass


def resolve_field_def(context, type, field_nodes):
    pass


def get_argument_defs(field, param):
    pass


def compile_object_type(
    context: CompilationContext,
    type: GraphQLObjectType,
    field_nodes: List[Field],
    origin_paths: List[str],
    destination_paths: List[str],
    response_path: Optional[str],
    error_destination: str,
    field_map: Dict[str, List[Field]],
    always_defer: bool,
) -> str:
    body = "("
    if isinstance(type.is_type_of, Callable) and not always_defer:
        context.isTypeOfs[type.name + "IsTypeOf"] = type.is_type_of
        body += """
!${GLOBAL_EXECUTION_CONTEXT}.isTypeOfs["${
      type.name
    }IsTypeOf"](${originPaths.join(
      "."
    )}) ? (${errorDestination}.push(${createErrorObject(
      context,
      fieldNodes,
      responsePath as any,
      ``Expected value of type "${
        type.name
      }" but got: ${${GLOBAL_INSPECT_NAME}(${originPaths.join(".")})}.``
    )}), null) :        
        """
        body += "{"
        for name, field_nodes in field_map.items():
            field = resolve_field_def(context, type, field_nodes)
            if not field:
                continue
            body += "${name}, "

            if field == TypeNameMetaFieldDef:
                body += "${type.name}, "
                continue

            resolver = field.resolve
            if not resolver and always_defer:
                field_name = field.name
                resolver = lambda parent: parent and parent[field_name]

            if resolver:
                context.deferred.append(
                    DeferredField(
                        name=name,
                        responsePath=add_path(response_path, name),
                        originPaths=origin_paths,
                        destinationPaths=destination_paths,
                        parentType=type,
                        fieldName=field.name,
                        fieldType=field.return_type,
                        fieldNodes=field_nodes,
                        args=get_argument_defs(field, field_nodes[0]),
                    )
                )
            else:
                body += compile_type(
                    context,
                    field.type,
                    field_nodes,
                    origin_paths,
                    destination_paths,
                    add_path(response_path, name),
                )
        body += ","
    body += "})"
    return body


def compile_deferred_fields(context: CompilationContext):
    pass


def generate_unique_declarations(context: CompilationContext, param):
    pass


def create_bound_query(
    context: CompilationContext,
    document: Document,
    param,
    get_variables,
    operation_name: Optional[str] = None,
) -> Any:
    pass


def is_compiled_query(prepared) -> bool:
    pass


def compile_deferred_fields_serially(context: CompilationContext):
    pass


def compile_type(context: CompilationContext, parent_type: GraphQLContext, field_nodes: List[Field], origin_paths:
List[str], destination_paths: List[str], previous_path: ObjectPath) -> str:
    pass
