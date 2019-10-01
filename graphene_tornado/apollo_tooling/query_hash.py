import hashlib


def compute(query):
    # type (str) -> str
    """
    Computes the query hash via SHA-256.

    Args:
        query: The query

    Returns:
        The query hash
    """
    return hashlib.sha256(query.encode()).hexdigest()
