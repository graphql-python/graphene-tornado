import collections

from graphene_tornado.apollo_tooling.operation_id import default_engine_reporting_signature
from graphene_tornado.request_context import SIGNATURE


class _LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.cache = collections.OrderedDict()

    def get(self, key, default=None):
        try:
            value = self.cache.pop(key)
            self.cache[key] = value
            return value
        except KeyError:
            return default

    def set(self, key, value):
        try:
            self.cache.pop(key)
        except KeyError:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)
        self.cache[key] = value


_SIGNATURE_CACHE = _LRUCache(10000)


def get_signature(request_context, operation_name, document, query_string):
    """
    Args:
        request_context: The request context
        operation_name: The operation name
        document: The document
        query_string: The query string
    Returns:
        The signature for the query
    """
    signature = request_context.get(SIGNATURE, None)
    if signature is None:
        signature = _SIGNATURE_CACHE.get(query_string)
    if signature is None:
        if document:
            calculate_signature = default_engine_reporting_signature
            signature = calculate_signature(document.document_ast, operation_name)
        elif query_string:
            signature = query_string
        request_context[SIGNATURE] = signature
    return signature


