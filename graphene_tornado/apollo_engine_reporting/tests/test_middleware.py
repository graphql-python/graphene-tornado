from graphql import get_default_backend, parse, build_ast_schema, execute

type_defs = """
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

query = """
    query q {
      author(id: 5) {
        name
        posts(limit: 2) {
          id
        }
      }
      aBoolean
    }
"""

APOLLO_PATH = [
    'author',
    'name',
    'posts',
    'id',
    'id',
    'aBoolean'
]

PATHS = []


def middleware(next, root, info, **args):
    PATHS.append(info.path[0])
    return next(root, info, **args)


def test_trace():
    schema = build_ast_schema(parse(type_defs))
    document = get_default_backend().document_from_string(schema, query)
    result = execute(schema, document.document_ast, middleware=[middleware])
    assert not result.errors

    # Graphene middlware doesn't seem to visit the same number of fields as Apollo?
    assert APOLLO_PATH == PATHS
