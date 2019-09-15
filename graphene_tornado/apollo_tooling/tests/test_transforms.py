from graphql import parse

from graphene_tornado.apollo_tooling.transforms import print_with_reduced_whitespace, hide_literals


def test_print_with_reduced_whitespace():
    doc = parse('''
        query Foo($a: Int) {
          user(
            name: "   tab->	yay"
          ) {
            name
          }
        }        
    ''')
    transformed = print_with_reduced_whitespace(doc)
    assert 'query Foo($a:Int){user(name:"   tab->\tyay"){name}}' == transformed


def test_hide_literals():
    doc = parse('''
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
        fragment Bar on User {
          age @skip(if: $a)
          ...Nested
        }
        fragment Nested on User {
          blah
        }    
    ''')
    transformed = print_with_reduced_whitespace(hide_literals(doc))
    assert 'query Foo($b:Int,$a:Boolean){user(name:"",age:0){...Bar...on User{hello bee}tz aliased:name}}fragment ' \
           'Bar on User{age@skip(if:$a)...Nested}fragment Nested on User{blah}' == transformed




