import json
from urllib import urlencode

from hamcrest import assert_that, equal_to
from tornado.httpclient import HTTPError
from tornado.testing import gen_test

from graphene_tornado.tests.base_test_case import BaseTestCase


class TestGraphQL(BaseTestCase):

    graphql_header = {'Content-Type': 'application/graphql'}
    form_header = {'Content-Type': 'application/x-www-form-urlencoded'}

    def url_string(self, string='/graphql', **url_params):
        if url_params:
            string += '?' + urlencode(url_params)

        return string

    def batch_url_string(self, **url_params):
        return self.url_string('/graphql/batch', **url_params)

    def response_json(self, response):
        return json.loads(response.body)

    @gen_test
    def test_allows_get_with_query_param(self):
        response = yield self.get(self.url_string(query='{test}'), headers=self.graphql_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello World"}
        }))

    @gen_test
    def test_allows_get_with_variable_values(self):
        response = yield self.get(self.url_string(
            query='query helloWho($who: String){ test(who: $who) }',
            variables=json.dumps({'who': "Dolly"})
        ), headers=self.graphql_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello Dolly"}
        }))

    @gen_test
    def test_allows_get_with_operation_name(self):
        response = yield self.get(self.url_string(
            query='''
            query helloYou { test(who: "You"), ...shared }
            query helloWorld { test(who: "World"), ...shared }
            query helloDolly { test(who: "Dolly"), ...shared }
            fragment shared on QueryRoot {
              shared: test(who: "Everyone")
            }
            ''',
            operationName='helloWorld'
        ), headers=self.graphql_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {
                'test': 'Hello World',
                'shared': 'Hello Everyone'
            }
        }))

    @gen_test
    def test_reports_validation_errors(self):
        with self.assertRaises(HTTPError) as context:
            yield self.get(self.url_string(
                query='{ test, unknownOne, unknownTwo }'
            ), headers=self.graphql_header)

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
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
        }))

    @gen_test
    def test_errors_when_missing_operation_name(self):
        with self.assertRaises(HTTPError) as context:
            yield self.get(self.url_string(
                query='''
                query TestQuery { test }
                mutation TestMutation { writeTest { test } }
                '''
            ))

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [
                {
                    'message': 'Must provide operation name if query contains multiple operations.'
                }
            ]
        }))

    @gen_test
    def test_errors_when_sending_a_mutation_via_get(self):
        with self.assertRaises(HTTPError) as context:
            yield self.get(self.url_string(
                query='''
                mutation TestMutation { writeTest { test } }
                '''
            ), headers=self.graphql_header)

        assert_that(context.exception.code, equal_to(405))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [
                {
                    'message': 'Can only perform a mutation operation from a POST request.'
                }
            ]
        }))

    @gen_test
    def test_errors_when_selecting_a_mutation_within_a_get(self):
        with self.assertRaises(HTTPError) as context:
            yield self.get(self.url_string(
                query='''
                query TestQuery { test }
                mutation TestMutation { writeTest { test } }
                ''',
                operationName='TestMutation'
            ), headers=self.graphql_header)

        assert_that(context.exception.code, equal_to(405))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [
                {
                    'message': 'Can only perform a mutation operation from a POST request.'
                }
            ]
        }))

    @gen_test
    def test_allows_mutation_to_exist_within_a_get(self):
        response = yield self.get(self.url_string(
            query='''
            query TestQuery { test }
            mutation TestMutation { writeTest { test } }
            ''',
            operationName='TestQuery'
        ), headers=self.graphql_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello World"}
        }))

    @gen_test
    def test_allows_post_with_json_encoding(self):
        response = yield self.post_json(self.url_string(), dict(query='{test}'))

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello World"}
        }))

    @gen_test
    def test_batch_allows_post_with_json_encoding(self):
        response = yield self.post_json(self.batch_url_string(), [dict(id=1, query='{test}')])

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to([{
            'id': 1,
            'data': {'test': "Hello World"},
            'status': 200,
        }]))

    @gen_test
    def test_batch_fails_if_is_empty(self):
        with self.assertRaises(HTTPError) as context:
            yield self.post_body(self.batch_url_string(), body='[]', headers={'Content-Type': 'application/json'})

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [{'message': 'Received an empty list in the batch request.'}]
        }))

    @gen_test
    def test_allows_sending_a_mutation_via_post(self):
        response = yield self.post_json(self.url_string(), dict(query='mutation TestMutation { writeTest { test } }'))

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'writeTest': {'test': 'Hello World'}}
        }))

    @gen_test
    def test_allows_post_with_url_encoding(self):
        response = yield self.post_body(self.url_string(), body=urlencode(dict(query='{test}')),
                                        headers=self.form_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello World"}
        }))

    @gen_test
    def test_supports_post_json_query_with_string_variables(self):
        response = yield self.post_json(self.url_string(), dict(
            query='query helloWho($who: String){ test(who: $who) }',
            variables=json.dumps({'who': "Dolly"})
        ))

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello Dolly"}
        }))

    @gen_test
    def test_batch_supports_post_json_query_with_string_variables(self):
        response = yield self.post_json(self.batch_url_string(), [dict(
            id=1,
            query='query helloWho($who: String){ test(who: $who) }',
            variables={'who': "Dolly"}
        )])

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to([{
            'id': 1,
            'data': {'test': "Hello Dolly"},
            'status': 200,
        }]))

    @gen_test
    def test_supports_post_json_query_with_json_variables(self):
        response = yield self.post_json(self.url_string(), dict(
            query='query helloWho($who: String){ test(who: $who) }',
            variables={'who': "Dolly"}
        ))

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello Dolly"}
        }))

    @gen_test
    def test_batch_supports_post_json_query_with_json_variables(self):
        response = yield self.post_json(self.batch_url_string(), [dict(
            id=1,
            query='query helloWho($who: String){ test(who: $who) }',
            variables={'who': "Dolly"}
        )])

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to([{
            'id': 1,
            'data': {'test': "Hello Dolly"},
            'status': 200,
        }]))

    @gen_test
    def test_supports_post_url_encoded_query_with_string_variables(self):
        response = yield self.post_body(self.url_string(), body=urlencode(dict(
            query='query helloWho($who: String){ test(who: $who) }',
            variables=json.dumps({'who': "Dolly"})
        )), headers=self.form_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello Dolly"}
        }))

    @gen_test
    def test_supports_post_json_quey_with_get_variable_values(self):
        response = yield self.post_json(self.url_string(
            variables=json.dumps({'who': "Dolly"})
        ), dict(
            query='query helloWho($who: String){ test(who: $who) }',
        ))

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello Dolly"}
        }))

    @gen_test
    def test_post_url_encoded_query_with_get_variable_values(self):
        response = yield self.post_body(self.url_string(
            variables=json.dumps({'who': "Dolly"})
        ), body=urlencode(dict(
            query='query helloWho($who: String){ test(who: $who) }',
        )), headers=self.form_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello Dolly"}
        }))

    @gen_test
    def test_supports_post_raw_text_query_with_get_variable_values(self):
        response = yield self.post_body(self.url_string(
            variables=json.dumps({'who': "Dolly"})
        ),
            body='query helloWho($who: String){ test(who: $who) }',
            headers=self.graphql_header
        )

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {'test': "Hello Dolly"}
        }))

    @gen_test
    def test_allows_post_with_operation_name(self):
        response = yield self.post_json(self.url_string(), dict(
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

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {
                'test': 'Hello World',
                'shared': 'Hello Everyone'
            }
        }))

    @gen_test
    def test_batch_allows_post_with_operation_name(self):
        response = yield self.post_json(self.batch_url_string(), [dict(
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

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to([{
            'id': 1,
            'data': {
                'test': 'Hello World',
                'shared': 'Hello Everyone'
            },
            'status': 200,
        }]))

    @gen_test
    def test_allows_post_with_get_operation_name(self):
        response = yield self.post_body(self.url_string(
            operationName='helloWorld'
        ), body='''
        query helloYou { test(who: "You"), ...shared }
        query helloWorld { test(who: "World"), ...shared }
        query helloDolly { test(who: "Dolly"), ...shared }
        fragment shared on QueryRoot {
          shared: test(who: "Everyone")
        }
        ''', headers=self.graphql_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {
                'test': 'Hello World',
                'shared': 'Hello Everyone'
            }
        }))

    @gen_test
    def test_supports_pretty_printing(self):
        response = yield self.get(self.url_string(query='{test}', pretty=True), headers=self.graphql_header)

        assert_that(response.body, equal_to(
            '{\n'
            '  "data": {\n'
            '    "test": "Hello World"\n'
            '  }\n'
            '}'
        ))

    @gen_test
    def test_supports_pretty_printing_by_request(self):
        response = yield self.get(self.url_string(query='{test}', pretty='1'), headers=self.graphql_header)

        assert_that(response.body, equal_to(
            '{\n'
            '  "data": {\n'
            '    "test": "Hello World"\n'
            '  }\n'
            '}'
        ))

    @gen_test
    def test_handles_field_errors_caught_by_graphql(self):
        response = yield self.get(self.url_string(query='{thrower}'), headers=self.graphql_header)
        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': None,
            'errors': [{'locations': [{'column': 2, 'line': 1}], 'message': 'Throws!'}]
        }))

    @gen_test
    def test_handles_syntax_errors_caught_by_graphql(self):
        with self.assertRaises(HTTPError) as context:
            yield self.get(self.url_string(query='syntaxerror'), headers=self.graphql_header)
        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [{'locations': [{'column': 1, 'line': 1}],
                        'message': 'Syntax Error GraphQL request (1:1) '
                                   'Unexpected Name "syntaxerror"\n\n1: syntaxerror\n   ^\n'}]
        }))

    @gen_test
    def test_handles_errors_caused_by_a_lack_of_query(self):
        with self.assertRaises(HTTPError) as context:
            yield self.get(self.url_string(), headers=self.graphql_header)

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [{'message': 'Must provide query string.'}]
        }))

    @gen_test
    def test_handles_not_expected_json_bodies(self):
        with self.assertRaises(HTTPError) as context:
            yield self.post_body(self.url_string(), body='[]', headers={'Content-Type': 'application/json'})

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [{'message': 'The received data is not a valid JSON query.'}]
        }))

    @gen_test
    def test_handles_invalid_json_bodies(self):
        with self.assertRaises(HTTPError) as context:
            yield self.post_body(self.url_string(), body='[oh}', headers={'Content-Type': 'application/json'})

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [{'message': 'POST body sent invalid JSON.'}]
        }))

    @gen_test
    def test_handles_incomplete_json_bodies(self):
        with self.assertRaises(HTTPError) as context:
            yield self.post_body(self.url_string(), body='{"query":', headers={'Content-Type': 'application/json'})

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [{'message': 'POST body sent invalid JSON.'}]
        }))

    @gen_test
    def test_handles_plain_post_text(self):
        with self.assertRaises(HTTPError) as context:
            yield self.post_body(self.url_string(
                variables=json.dumps({'who': "Dolly"})
            ),
                body='query helloWho($who: String){ test(who: $who) }',
                headers={'Content-Type': 'text/plain'}
            )

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [{'message': 'Must provide query string.'}]
        }))

    @gen_test
    def test_handles_poorly_formed_variables(self):
        with self.assertRaises(HTTPError) as context:
            yield self.get(self.url_string(
                query='query helloWho($who: String){ test(who: $who) }',
                variables='who:You'
            ), headers=self.graphql_header)

        assert_that(context.exception.code, equal_to(400))
        assert_that(self.response_json(context.exception.response), equal_to({
            'errors': [{'message': 'Variables are invalid JSON.'}]
        }))

    @gen_test
    def test_handles_unsupported_http_methods(self):
        with self.assertRaises(HTTPError) as context:
            yield self.put(self.url_string(query='{test}'), '', headers=self.graphql_header)
        assert_that(context.exception.code, equal_to(405))

    @gen_test
    def test_passes_request_into_context_request(self):
        response = yield self.get(self.url_string(query='{request}', q='testing'), headers=self.graphql_header)

        assert_that(response.code, equal_to(200))
        assert_that(self.response_json(response), equal_to({
            'data': {
                'request': 'testing'
            }
        }))


