"""
Ported from https://github.com/apollographql/apollo-tooling/blob/master/packages/apollo-graphql/src/transforms.ts
"""
import re

import six

from graphql import print_ast
from graphql.language.ast import Document, IntValue, FloatValue, StringValue, ListValue, ObjectValue, Field, \
    Directive, FragmentDefinition, InlineFragment, FragmentSpread, SelectionSet, OperationDefinition
from graphql.language.visitor import Visitor, visit

from graphene_tornado.apollo_tooling.seperate_operations import separate_operations


def hide_literals(ast):
    # type: (Document) -> Document
    """
    Replace numeric, string, list, and object literals with "empty"
    values. Leaves enums alone (since there's no consistent "zero" enum). This
    can help combine similar queries if you substitute values directly into
    queries rather than use GraphQL variables, and can hide sensitive data in
    your query (say, a hardcoded API key) from Engine servers, but in general
    avoiding those situations is better than working around them.
    """
    visit(ast, _HIDE_LITERALS_VISITOR)
    return ast


def hide_string_and_numeric_literals(ast):
    # type: (Document) -> Document
    """
    In the same spirit as the similarly named `hideLiterals` function, only
    hide string and numeric literals.
    """
    visit(ast, _HIDE_ONLY_STRING_AND_NUMERIC_LITERALS_VISITOR)
    return ast


def drop_unused_definitions(ast, operation_name):
    # type: (Document, str) -> Document
    """
    A GraphQL query may contain multiple named operations, with the operation to
    use specified separately by the client. This transformation drops unused
    operations from the query, as well as any fragment definitions that are not
    referenced.  (In general we recommend that unused definitions are dropped on
    the client before sending to the server to save bandwidth and parsing time.)
    """
    separated = separate_operations(ast).get(operation_name, None)
    if not separated:
        return ast
    return separated


def sort_ast(ast):
    # type: (Document) -> Document
    """
    sortAST sorts most multi-child nodes alphabetically. Using this as part of
    your signature calculation function may make it easier to tell the difference
    between queries that are similar to each other, and if for some reason your
    QraphQL client generates query strings with elements in nondeterministic
    order, it can make sure the queries are treated as identical.
    """
    visit(ast, _SORTING_VISITOR)
    return ast


def remove_aliases(ast):
    # type: (Document) -> Document
    """
    removeAliases gets rid of GraphQL aliases, a feature by which you can tell a
    server to return a field's data under a different name from the field
    name. Maybe this is useful if somebody somewhere inserts random aliases into
    their queries.
    """
    visit(ast, _REMOVE_ALIAS_VISITOR)
    return ast


def print_with_reduced_whitespace(ast):
    # type: (Document) -> str
    """
    Like the graphql-js print function, but deleting whitespace wherever
    feasible. Specifically, all whitespace (outside of string literals) is
    reduced to at most one space, and even that space is removed anywhere except
    for between two alphanumerics.
    """
    visit(ast, _HEX_CONVERSION_VISITOR)
    val = re.sub(r'\s+', ' ',  print_ast(ast))

    val = re.sub(r'([^_a-zA-Z0-9]) ', _replace_with_first_group, val)
    val = re.sub(r' ([^_a-zA-Z0-9])', _replace_with_first_group, val)
    val = re.sub(r'"([a-f0-9]+)"', _from_hex, val)

    return val


def _replace_with_first_group(match):
    return match.group(1)


def _from_hex(match):
    m = match.group(1)
    if six.PY3:
        m = bytes.fromhex(m).decode('utf-8')
    else:
        m = m.decode('hex').encode('utf-8')
    return '"' + m + '"'


def _sorted(items, key):
    if items is not None:
        return sorted(items, key=key)
    return None


class _HideLiteralsVisitor(Visitor):

    def __init__(self, only_string_and_numeric=False):
        super(_HideLiteralsVisitor, self).__init__()
        self._only_string_and_numeric = only_string_and_numeric

    def enter(self, node, key, parent, path, ancestors):
        if isinstance(node, IntValue):
            node.value = 0
        elif isinstance(node, FloatValue):
            node.value = 0
        elif isinstance(node, StringValue):
            node.value = ""
        elif not self._only_string_and_numeric and isinstance(node, ListValue):
            node.values = []
        elif not self._only_string_and_numeric and isinstance(node, ObjectValue):
            node.fields = []
        return node


_HIDE_LITERALS_VISITOR = _HideLiteralsVisitor()
_HIDE_ONLY_STRING_AND_NUMERIC_LITERALS_VISITOR = _HideLiteralsVisitor(only_string_and_numeric=True)


class _RemoveAliasesVisitor(Visitor):

    def enter(self, node, key, parent, path, ancestors):
        if isinstance(node, Field):
           node.alias = None
        return node


_REMOVE_ALIAS_VISITOR = _RemoveAliasesVisitor()


class _HexConversionVisitor(Visitor):

    def enter(self, node, key, parent, path, ancestors):
        if isinstance(node, StringValue) and node.value is not None:
            if six.PY3:
                encoded = node.value.encode('utf-8').hex()
            else:
                encoded = node.value.encode('hex')
            node.value = encoded
        return node


_HEX_CONVERSION_VISITOR = _HexConversionVisitor()


class _SortingVisitor(Visitor):

    def enter(self, node, key, parent, path, ancestors):
        if isinstance(node, Document):
            node.definitions = _sorted(node.definitions, lambda x: (x.__class__.__name__, self._by_name(x)))
        elif isinstance(node, OperationDefinition):
            node.variable_definitions = _sorted(node.variable_definitions, self._by_variable_name)
        elif isinstance(node, SelectionSet):
            node.selections = _sorted(node.selections, lambda x: (x.__class__.__name__, self._by_name(x)))
        elif isinstance(node, Field):
            node.arguments = _sorted(node.arguments, self._by_name)
        elif isinstance(node, FragmentSpread):
            node.directives = _sorted(node.directives, self._by_name)
        elif isinstance(node, InlineFragment):
            node.directives = _sorted(node.directives, self._by_type_definition)
        elif isinstance(node, FragmentDefinition):
            node.directives = _sorted(node.directives, self._by_name)
        elif isinstance(node, Directive):
            node.arguments = _sorted(node.arguments, self._by_name)
        return node

    def _by_name(self, node):
        if isinstance(node, InlineFragment):
            return self._by_type_definition(node)
        elif node.name is not None:
            return node.name.value
        return None

    def _by_type_definition(self, node):
        if node.type_condition is not None and node.type_condition.name:
            return node.type_condition.name.value
        return None

    def _by_variable_name(self, node):
        if node.variable is not None and node.variable.name is not None:
            return node.variable.name.value
        return None


_SORTING_VISITOR = _SortingVisitor()
