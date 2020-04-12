from __future__ import absolute_import
from __future__ import print_function

import hashlib
from typing import cast

from graphene.types.schema import introspection_query
from graphql import execute
from graphql import ExecutionResult
from graphql import GraphQLError
from graphql import GraphQLSchema
from graphql import parse
from json_stable_stringify_python import stringify


def generate_schema_hash(schema: GraphQLSchema) -> str:
    """
    Generates a stable hash of the current schema using an introspection query.
    """
    ast = parse(introspection_query)
    result = cast(ExecutionResult, execute(schema, ast))

    if result and not result.data:
        raise GraphQLError("Unable to generate server introspection document")

    schema = result.data["__schema"]
    # It's important that we perform a deterministic stringification here
    # since, depending on changes in the underlying `graphql-core` execution
    # layer, varying orders of the properties in the introspection
    stringified_schema = stringify(schema).encode("utf-8")
    return hashlib.sha512(stringified_schema).hexdigest()
