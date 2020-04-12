from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from graphql.type.definition import GraphQLArgument
from graphql.type.definition import GraphQLField
from graphql.type.definition import GraphQLNonNull
from graphql.type.definition import GraphQLObjectType
from graphql.type.scalars import GraphQLString
from graphql.type.schema import GraphQLSchema
from tornado.gen import coroutine
from tornado.gen import Return


async def resolve_raises(*_):
    raise Exception("Throws!")


async def resolve1(obj, args, context, info):
    return context.args.get("q")


async def resolve2(obj, args, context, info):
    return context


async def resolve3(obj, args, context, info):
    return "Hello %s" % (args.get("who") or "World")


QueryRootType = GraphQLObjectType(
    name="QueryRoot",
    fields={
        "thrower": GraphQLField(GraphQLNonNull(GraphQLString), resolver=resolve_raises),
        "request": GraphQLField(GraphQLNonNull(GraphQLString), resolver=resolve1),
        "context": GraphQLField(GraphQLNonNull(GraphQLString), resolver=resolve2),
        "test": GraphQLField(
            type=GraphQLString,
            args={"who": GraphQLArgument(GraphQLString)},
            resolver=resolve3,
        ),
    },
)

MutationRootType = GraphQLObjectType(
    name="MutationRoot",
    fields={
        "writeTest": GraphQLField(type=QueryRootType, resolver=lambda *_: QueryRootType)
    },
)

Schema = GraphQLSchema(QueryRootType, MutationRootType)
