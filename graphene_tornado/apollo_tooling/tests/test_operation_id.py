from graphql import parse

from graphene_tornado.apollo_tooling.operation_id import default_engine_reporting_signature


def test_basic_signature():
    operation = ""
    doc = parse("""
        {
          user {
            name
          }
        }    
    """)
    assert "{user{name}}" == default_engine_reporting_signature(doc, operation)


def test_basic_signature_with_query():
    operation = ""
    doc = parse("""
        query {
          user {
            name
          }
        }    
    """)
    assert "{user{name}}" == default_engine_reporting_signature(doc, operation)


def test_basic_signature_with_operation_name():
    operation = "OpName"
    doc = parse("""
        query OpName {
          user {
            name
          }
        }
    """)
    assert "query OpName{user{name}}" == default_engine_reporting_signature(doc, operation)


def test_basic_signature_with_fragment():
    operation = ""
    doc = parse("""
        {
          user {
            name
            ...Bar
          }
        }
        fragment Bar on User {
          asd
        }
        fragment Baz on User {
          jkl
        }
    """)
    assert "fragment Bar on User{asd}{user{name...Bar}}" == default_engine_reporting_signature(doc, operation)


def test_basic_signature_with_fragments_in_various_order():
    operation = ""
    doc = parse("""
        fragment Bar on User {
          asd
        }
        {
          user {
            name
            ...Bar
          }
        }
        fragment Baz on User {
          jkl
        }
    """)
    assert "fragment Bar on User{asd}{user{name...Bar}}" == default_engine_reporting_signature(doc, operation)


def test_basic_signature_with_full_test():
    operation = "Foo"
    doc = parse("""
        query Foo($b: Int, $a: Boolean) {
          user(name: "hello", age: 5) {
            ...Bar
            ... on User {
              hello
              bee
            }
            tz
            aliased: name
          }
        }
        fragment Baz on User {
          asd
        }
        fragment Bar on User {
          age @skip(if: $a)
          ...Nested
        }
        fragment Nested on User {
          blah
        }
    """)
    assert "fragment Bar on User{age@skip(if:$a)...Nested}fragment Nested on User{blah}query Foo($a:Boolean,$b:Int)" \
           "{user(age:0,name:\"\"){name tz...Bar...on User{bee hello}}}"\
           == default_engine_reporting_signature(doc, operation)


def test_basic_signature_with_various_argument_types():
    operation = "OpName"
    doc = parse("""
        query OpName($c: Int!, $a: [[Boolean!]!], $b: EnumType) {
          user {
            name(apple: $a, cat: $c, bag: $b)
          }
        }
    """)
    assert "query OpName($a:[[Boolean!]!],$b:EnumType,$c:Int!){user{name(apple:$a,bag:$b,cat:$c)}}" \
           == default_engine_reporting_signature(doc, operation)


def test_basic_signature_with_inline_types():
    operation = "OpName"
    doc = parse("""
        query OpName {
          user {
            name(apple: [[10]], cat: ENUM_VALUE, bag: { input: "value" })
          }
        }
    """)
    assert "query OpName{user{name(apple:[],bag:{},cat:ENUM_VALUE)}}" == \
           default_engine_reporting_signature(doc, operation)



