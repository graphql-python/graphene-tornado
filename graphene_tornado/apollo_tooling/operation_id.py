"""
Ported from https://github.com/apollographql/apollo-tooling/blob/master/packages/apollo-graphql/src/operationId.ts
"""
from graphene_tornado.apollo_tooling.transforms import print_with_reduced_whitespace, sort_ast, remove_aliases, hide_literals, \
    drop_unused_definitions
from graphql.language.ast import DocumentNode
from typing import Optional


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
