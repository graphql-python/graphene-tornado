from __future__ import absolute_import, division, print_function

import json

from six.moves.urllib.parse import urlencode

import pytest
from tornado.escape import to_unicode
from tornado.httpclient import HTTPError

from examples.example import ExampleApplication
from graphene_tornado.tests.http_helper import HttpHelper

GRAPHQL_HEADER = {'Content-Type': 'application/graphql'}
FORM_HEADER = {'Content-Type': 'application/x-www-form-urlencoded'}


@pytest.fixture
def app():
    return ExampleApplication()


@pytest.fixture
def http_helper(http_client, base_url):
    return HttpHelper(http_client, base_url)


@pytest.mark.gen_test
def test_allows_get_with_query_param(http_helper):
    response = yield http_helper.get(url_string(query='{test}'), headers=GRAPHQL_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello World"}
    }


@pytest.mark.gen_test
def test_allows_get_with_variable_values(http_helper):
    response = yield http_helper.get(url_string(
        query='query helloWho($who: String){ test(who: $who) }',
        variables=json.dumps({'who': "Dolly"})
    ), headers=GRAPHQL_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello Dolly"}
    }


@pytest.mark.gen_test
def test_allows_get_with_operation_name(http_helper):
    response = yield http_helper.get(url_string(
        query='''
            query helloYou { test(who: "You"), ...shared }
            query helloWorld { test(who: "World"), ...shared }
            query helloDolly { test(who: "Dolly"), ...shared }
            fragment shared on QueryRoot {
              shared: test(who: "Everyone")
            }
            ''',
        operationName='helloWorld'
    ), headers=GRAPHQL_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {
            'test': 'Hello World',
            'shared': 'Hello Everyone'
        }
    }


@pytest.mark.gen_test
def test_reports_validation_errors(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.get(url_string(
            query='{ test, unknownOne, unknownTwo }'
        ), headers=GRAPHQL_HEADER)

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [
            {
                'message': 'Cannot query field "unknownOne" on type "QueryRoot".',
                'locations': [{'line': 1, 'column': 9}]
            },
            {
                'message': 'Cannot query field "unknownTwo" on type "QueryRoot".',
                'locations': [{'line': 1, 'column': 21}]
            }
        ]
    }


@pytest.mark.gen_test
def test_errors_when_missing_operation_name(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.get(url_string(
            query='''
                query TestQuery { test }
                mutation TestMutation { writeTest { test } }
                '''
        ))

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [
            {
                'message': 'Must provide operation name if query contains multiple operations.'
            }
        ]
    }


@pytest.mark.gen_test
def test_errors_when_sending_a_mutation_via_get(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.get(url_string(
            query='''
                mutation TestMutation { writeTest { test } }
                '''
        ), headers=GRAPHQL_HEADER)

    assert context.value.code == 405
    assert response_json(context.value.response) == {
        'errors': [
            {
                'message': 'Can only perform a mutation operation from a POST request.'
            }
        ]
    }


@pytest.mark.gen_test
def test_errors_when_selecting_a_mutation_within_a_get(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.get(url_string(
            query='''
                query TestQuery { test }
                mutation TestMutation { writeTest { test } }
                ''',
            operationName='TestMutation'
        ), headers=GRAPHQL_HEADER)

    assert context.value.code == 405
    assert response_json(context.value.response) == {
        'errors': [
            {
                'message': 'Can only perform a mutation operation from a POST request.'
            }
        ]
    }


@pytest.mark.gen_test
def test_allows_mutation_to_exist_within_a_get(http_helper):
    response = yield http_helper.get(url_string(
        query='''
            query TestQuery { test }
            mutation TestMutation { writeTest { test } }
            ''',
        operationName='TestQuery'
    ), headers=GRAPHQL_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello World"}
    }


@pytest.mark.gen_test
def test_allows_post_with_json_encoding(http_helper):
    response = yield http_helper.post_json(url_string(), dict(query='{test}'))

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello World"}
    }


@pytest.mark.gen_test
def test_batch_allows_post_with_json_encoding(http_helper):
    response = yield http_helper.post_json(batch_url_string(), [dict(id=1, query='{test}')])

    assert response.code == 200
    assert response_json(response) == [{
        'id': 1,
        'data': {'test': "Hello World"},
        'status': 200,
    }]


@pytest.mark.gen_test
def test_batch_fails_if_is_empty(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.post_body(batch_url_string(), body='[]', headers={'Content-Type': 'application/json'})

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [{'message': 'Received an empty list in the batch request.'}]
    }


@pytest.mark.gen_test
def test_allows_sending_a_mutation_via_post(http_helper):
    response = yield http_helper.post_json(url_string(), dict(query='mutation TestMutation { writeTest { test } }'))

    assert response.code == 200
    assert response_json(response) == {
        'data': {'writeTest': {'test': 'Hello World'}}
    }


@pytest.mark.gen_test
def test_allows_post_with_url_encoding(http_helper):
    response = yield http_helper.post_body(url_string(), body=urlencode(dict(query='{test}')), headers=FORM_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello World"}
    }


@pytest.mark.gen_test
def test_supports_post_json_query_with_string_variables(http_helper):
    response = yield http_helper.post_json(url_string(), dict(
        query='query helloWho($who: String){ test(who: $who) }',
        variables=json.dumps({'who': "Dolly"})
    ))

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello Dolly"}
    }


@pytest.mark.gen_test
def test_batch_supports_post_json_query_with_string_variables(http_helper):
    response = yield http_helper.post_json(batch_url_string(), [dict(
        id=1,
        query='query helloWho($who: String){ test(who: $who) }',
        variables={'who': "Dolly"}
    )])

    assert response.code == 200
    assert response_json(response) == [{
        'id': 1,
        'data': {'test': "Hello Dolly"},
        'status': 200,
    }]


@pytest.mark.gen_test
def test_supports_post_json_query_with_json_variables(http_helper):
    response = yield http_helper.post_json(url_string(), dict(
        query='query helloWho($who: String){ test(who: $who) }',
        variables={'who': "Dolly"}
    ))

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello Dolly"}
    }


@pytest.mark.gen_test
def test_batch_supports_post_json_query_with_json_variables(http_helper):
    response = yield http_helper.post_json(batch_url_string(), [dict(
        id=1,
        query='query helloWho($who: String){ test(who: $who) }',
        variables={'who': "Dolly"}
    )])

    assert response.code == 200
    assert response_json(response) == [{
        'id': 1,
        'data': {'test': "Hello Dolly"},
        'status': 200,
    }]


@pytest.mark.gen_test
def test_supports_post_url_encoded_query_with_string_variables(http_helper):
    response = yield http_helper.post_body(url_string(), body=urlencode(dict(
        query='query helloWho($who: String){ test(who: $who) }',
        variables=json.dumps({'who': "Dolly"})
    )), headers=FORM_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello Dolly"}
    }


@pytest.mark.gen_test
def test_supports_post_json_quey_with_get_variable_values(http_helper):
    response = yield http_helper.post_json(url_string(
        variables=json.dumps({'who': "Dolly"})
    ), dict(
        query='query helloWho($who: String){ test(who: $who) }',
    ))

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello Dolly"}
    }


@pytest.mark.gen_test
def test_post_url_encoded_query_with_get_variable_values(http_helper):
    response = yield http_helper.post_body(url_string(
        variables=json.dumps({'who': "Dolly"})
    ), body=urlencode(dict(
        query='query helloWho($who: String){ test(who: $who) }',
    )), headers=FORM_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello Dolly"}
    }


@pytest.mark.gen_test
def test_supports_post_raw_text_query_with_get_variable_values(http_helper):
    response = yield http_helper.post_body(url_string(
        variables=json.dumps({'who': "Dolly"})
    ),
        body='query helloWho($who: String){ test(who: $who) }',
        headers=GRAPHQL_HEADER
    )

    assert response.code == 200
    assert response_json(response) == {
        'data': {'test': "Hello Dolly"}
    }


@pytest.mark.gen_test
def test_allows_post_with_operation_name(http_helper):
    response = yield http_helper.post_json(url_string(), dict(
        query='''
            query helloYou { test(who: "You"), ...shared }
            query helloWorld { test(who: "World"), ...shared }
            query helloDolly { test(who: "Dolly"), ...shared }
            fragment shared on QueryRoot {
              shared: test(who: "Everyone")
            }
            ''',
        operationName='helloWorld'
    ))

    assert response.code == 200
    assert response_json(response) == {
        'data': {
            'test': 'Hello World',
            'shared': 'Hello Everyone'
        }
    }


@pytest.mark.gen_test
def test_batch_allows_post_with_operation_name(http_helper):
    response = yield http_helper.post_json(batch_url_string(), [dict(
        id=1,
        query='''
            query helloYou { test(who: "You"), ...shared }
            query helloWorld { test(who: "World"), ...shared }
            query helloDolly { test(who: "Dolly"), ...shared }
            fragment shared on QueryRoot {
              shared: test(who: "Everyone")
            }
            ''',
        operationName='helloWorld'
    )])

    assert response.code == 200
    assert response_json(response) == [{
        'id': 1,
        'data': {
            'test': 'Hello World',
            'shared': 'Hello Everyone'
        },
        'status': 200,
    }]


@pytest.mark.gen_test
def test_allows_post_with_get_operation_name(http_helper):
    response = yield http_helper.post_body(url_string(
        operationName='helloWorld'
    ), body='''
        query helloYou { test(who: "You"), ...shared }
        query helloWorld { test(who: "World"), ...shared }
        query helloDolly { test(who: "Dolly"), ...shared }
        fragment shared on QueryRoot {
          shared: test(who: "Everyone")
        }
        ''', headers=GRAPHQL_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {
            'test': 'Hello World',
            'shared': 'Hello Everyone'
        }
    }


@pytest.mark.gen_test
def test_supports_pretty_printing(http_helper):
    response = yield http_helper.get(url_string(query='{test}', pretty=True), headers=GRAPHQL_HEADER)
    assert to_unicode(response.body) == """{
  "data": {
    "test": "Hello World"
  }
}"""


@pytest.mark.gen_test
def test_supports_pretty_printing_by_request(http_helper):
    response = yield http_helper.get(url_string(query='{test}', pretty='1'), headers=GRAPHQL_HEADER)
    assert to_unicode(response.body) == """{
  "data": {
    "test": "Hello World"
  }
}"""


@pytest.mark.gen_test
def test_handles_field_errors_caught_by_graphql(http_helper):
    response = yield http_helper.get(url_string(query='{thrower}'), headers=GRAPHQL_HEADER)
    assert response.code == 200
    assert response_json(response) == {
        'data': None,
        'errors': [{u'path': [u'thrower'], u'message': u'Throws!', u'locations': [{u'column': 2, u'line': 1}]}]
    }


@pytest.mark.gen_test
def test_handles_syntax_errors_caught_by_graphql(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.get(url_string(query='syntaxerror'), headers=GRAPHQL_HEADER)
    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [{'locations': [{'column': 1, 'line': 1}],
                    'message': 'Syntax Error GraphQL request (1:1) '
                               'Unexpected Name "syntaxerror"\n\n1: syntaxerror\n   ^\n'}]
    }


@pytest.mark.gen_test
def test_handles_errors_caused_by_a_lack_of_query(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.get(url_string(), headers=GRAPHQL_HEADER)

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [{'message': 'Must provide query string.'}]
    }


@pytest.mark.gen_test
def test_handles_not_expected_json_bodies(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.post_body(url_string(), body='[]', headers={'Content-Type': 'application/json'})

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [{'message': 'The received data is not a valid JSON query.'}]
    }


@pytest.mark.gen_test
def test_handles_invalid_json_bodies(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.post_body(url_string(), body='[oh}', headers={'Content-Type': 'application/json'})

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [{'message': 'POST body sent invalid JSON.'}]
    }


@pytest.mark.gen_test
def test_handles_incomplete_json_bodies(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.post_body(url_string(), body='{"query":', headers={'Content-Type': 'application/json'})

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [{'message': 'POST body sent invalid JSON.'}]
    }


@pytest.mark.gen_test
def test_handles_plain_post_text(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.post_body(url_string(
            variables=json.dumps({'who': "Dolly"})
        ),
            body='query helloWho($who: String){ test(who: $who) }',
            headers={'Content-Type': 'text/plain'}
        )

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [{'message': 'Must provide query string.'}]
    }


@pytest.mark.gen_test
def test_handles_poorly_formed_variables(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.get(url_string(
            query='query helloWho($who: String){ test(who: $who) }',
            variables='who:You'
        ), headers=GRAPHQL_HEADER)

    assert context.value.code == 400
    assert response_json(context.value.response) == {
        'errors': [{'message': 'Variables are invalid JSON.'}]
    }


@pytest.mark.gen_test
def test_handles_unsupported_http_methods(http_helper):
    with pytest.raises(HTTPError) as context:
        yield http_helper.put(url_string(query='{test}'), '', headers=GRAPHQL_HEADER)
    assert context.value.code == 405


@pytest.mark.gen_test
def test_passes_request_into_context_request(http_helper):
    response = yield http_helper.get(url_string(query='{request}', q='testing'), headers=GRAPHQL_HEADER)

    assert response.code == 200
    assert response_json(response) == {
        'data': {
            'request': 'testing'
        }
    }


def url_string(string='/graphql', **url_params):
    if url_params:
        string += '?' + urlencode(url_params)
    return string


def batch_url_string(**url_params):
    return url_string('/graphql/batch', **url_params)


def response_json(response):
    return json.loads(to_unicode(response.body))
