from __future__ import absolute_import, print_function

import hashlib

from graphene import Schema
from graphql import parse, execute, GraphQLError
from graphql.utils.introspection_query import introspection_query
from json_stable_stringify_python import stringify


def generate_schema_hash(schema: Schema) -> str:
    """
    Generates a stable hash of the current schema using an introspection query.
    """
    ast = parse(introspection_query)
    result = execute(schema, ast)

    if result and not result.data:
        raise GraphQLError('Unable to generate server introspection document')

    schema = result.data['__schema']
    # It's important that we perform a deterministic stringification here
    # since, depending on changes in the underlying `graphql-core` execution
    # layer, varying orders of the properties in the introspection
    stringified_schema = stringify(schema).encode('utf-8')
    return hashlib.sha512(stringified_schema).hexdigest()
