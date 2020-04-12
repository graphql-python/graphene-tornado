from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from typing import Optional

import graphene
from graphene import ObjectType
from graphene import Schema
from graphql.type.definition import GraphQLResolveInfo
from tornado.escape import to_unicode


class QueryRoot(ObjectType):

    thrower = graphene.String(required=True)
    request = graphene.String(required=True)
    test = graphene.String(who=graphene.String())

    def resolve_thrower(self, info):
        raise Exception("Throws!")

    def resolve_request(self, info: GraphQLResolveInfo) -> str:
        return to_unicode(info.context.arguments["q"][0])

    def resolve_test(self, info: GraphQLResolveInfo, who: Optional[str] = None) -> str:
        return "Hello %s" % (who or "World")


class MutationRoot(ObjectType):
    write_test = graphene.Field(QueryRoot)

    def resolve_write_test(self, info: GraphQLResolveInfo) -> QueryRoot:
        return QueryRoot()


schema = Schema(query=QueryRoot, mutation=MutationRoot)
