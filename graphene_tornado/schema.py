from __future__ import absolute_import, division, print_function

import graphene
from graphene import ObjectType, Schema
from tornado.escape import to_unicode
from graphql.type.definition import GraphQLResolveInfo
from typing import Optional


class QueryRoot(ObjectType):

    thrower = graphene.String(required=True)
    request = graphene.String(required=True)
    test = graphene.String(who=graphene.String())

    def resolve_thrower(self, info):
        raise Exception("Throws!")

    def resolve_request(self, info: GraphQLResolveInfo) -> str:
        return to_unicode(info.context.arguments['q'][0])

    def resolve_test(self, info: GraphQLResolveInfo, who: Optional[str]=None) -> str:
        return 'Hello %s' % (who or 'World')


class MutationRoot(ObjectType):
    write_test = graphene.Field(QueryRoot)

    def resolve_write_test(self, info: GraphQLResolveInfo) -> QueryRoot:
        return QueryRoot()


schema = Schema(query=QueryRoot, mutation=MutationRoot)
