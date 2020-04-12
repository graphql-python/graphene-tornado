"""
Ported from https://github.com/apollographql/apollo-tooling/blob/master/packages/apollo-graphql/src/operationId.ts
"""
from typing import Optional

from graphql.language.ast import DocumentNode

from graphene_tornado.apollo_tooling.transforms import drop_unused_definitions
from graphene_tornado.apollo_tooling.transforms import hide_literals
from graphene_tornado.apollo_tooling.transforms import print_with_reduced_whitespace
from graphene_tornado.apollo_tooling.transforms import remove_aliases
from graphene_tornado.apollo_tooling.transforms import sort_ast


def default_engine_reporting_signature(ast: DocumentNode, operation_name: str) -> str:
    """
    The engine reporting signature function consists of removing extra whitespace,
    sorting the AST in a deterministic manner, hiding literals, and removing
    unused definitions.
    """
    return print_with_reduced_whitespace(
        sort_ast(
            remove_aliases(hide_literals(drop_unused_definitions(ast, operation_name)))
        )
    )
