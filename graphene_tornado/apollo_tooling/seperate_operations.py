"""
Backported from graphql-core-next

https://github.com/graphql-python/graphql-core-next/blob/master/src/graphql/utilities/separate_operations.py
"""

from collections import defaultdict

from graphql.language.ast import Document, OperationDefinition, FragmentDefinition, FragmentSpread
from graphql.language.visitor import Visitor, visit
from typing import Dict, Set

__all__ = ["separate_operations"]


DepGraph = Dict[str, Set[str]]


def separate_operations(document_ast):
    """Separate operations in a given AST document.
    This function accepts a single AST document which may contain many operations and
    fragments and returns a collection of AST documents each of which contains a single
    operation as well the fragment definitions it refers to.
    """

    # Populate metadata and build a dependency graph.
    visitor = SeparateOperations()
    visit(document_ast, visitor)
    operations = visitor.operations
    fragments = visitor.fragments
    positions = visitor.positions
    dep_graph = visitor.dep_graph

    # For each operation, produce a new synthesized AST which includes only what is
    # necessary for completing that operation.
    separated_document_asts = {}
    for operation in operations:
        operation_name = op_name(operation)
        dependencies = set()
        collect_transitive_dependencies(dependencies, dep_graph, operation_name)

        # The list of definition nodes to be included for this operation, sorted to
        # retain the same order as the original document.
        definitions = [operation]
        for name in dependencies:
            definitions.append(fragments[name])
            definitions.sort(key=lambda n: positions.get(n, 0))

        separated_document_asts[operation_name] = Document(definitions=definitions)

    return separated_document_asts


class SeparateOperations(Visitor):

    def __init__(self):
        super(SeparateOperations, self).__init__()
        self.operations = []
        self.fragments = {}
        self.positions = {}
        self.dep_graph = defaultdict(set)
        self.from_name = None
        self.idx = 0

    def enter(self, node, key, parent, path, ancestors):
        if isinstance(node, OperationDefinition):
            self.from_name = op_name(node)
            self.operations.append(node)
            self.positions[node] = self.idx
            self.idx += 1
        elif isinstance(node, FragmentDefinition):
            self.from_name = node.name.value
            self.fragments[self.from_name] = node
            self.positions[node] = self.idx
            self.idx += 1
        elif isinstance(node, FragmentSpread):
            to_name = node.name.value
            self.dep_graph[self.from_name].add(to_name)
        return node


def op_name(operation):
    """Provide the empty string for anonymous operations."""
    return operation.name.value if operation.name else ""


def collect_transitive_dependencies(collected, dep_graph, from_name):
    """Collect transitive dependencies.
    From a dependency graph, collects a list of transitive dependencies by recursing
    through a dependency graph.
    """
    immediate_deps = dep_graph[from_name]
    for to_name in immediate_deps:
        if to_name not in collected:
            collected.add(to_name)
            collect_transitive_dependencies(collected, dep_graph, to_name)
