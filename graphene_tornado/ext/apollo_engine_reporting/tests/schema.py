from graphene import Field, List, Int, Boolean, String, ObjectType, Schema

SCHEMA_STRING = """
  schema {
      query: Query
  }
  
  type User {
    id: Int
    name: String
    posts(limit: Int): [Post]
  }
  type Post {
    id: Int
    title: String
    views: Int
    author: User
  }
  type Query {
    aString: String
    aBoolean: Boolean
    anInt: Int
    author(id: Int): User
    topPosts(limit: Int): [Post]
  }
"""


class User(ObjectType):

    id = Int()
    name = String()
    posts = Field(lambda: List(Post), limit=Int())

    async def get_node(self, info, id):
        return User(id=id)

    def resolve_posts(self, info, **args):
        return [Post(id=1), Post(id=2)]


class Post(ObjectType):
    """A ship in the Star Wars saga"""

    id = Int()
    title = String()
    views = Int()
    author = Field(User)

    async def get_node(self, info, **args):
        return Post(id=1)


class Query(ObjectType):
    a_string = Field(String, name='aString')
    a_boolean = Field(Boolean, name='aBoolean')
    an_int = Field(Int, name='anInt')
    author = Field(User, id=Int())
    top_posts = Field(List(Post), limit=Int())

    async def resolve_author(self, info, **args):
        return User()

    async def resolve_posts(self, info, **args):
        return [Post(id=1), Post(id=2)]


schema = Schema(query=Query)

