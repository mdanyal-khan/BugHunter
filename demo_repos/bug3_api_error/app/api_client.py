"""A tiny API client used for Demo Bug 3 (unhandled API exceptions).

`http_get` is injectable so tests can simulate success/failure without a
real network call or a mocking framework.
"""
import requests


class APIError(Exception):
    """Raised when the remote API cannot be reached or returns an error.

    (Defined here but never raised yet — that omission is the bug.)
    """


def fetch_status(url, http_get=None):
    """Fetches {"status": ...} from url and returns the status value.

    BUG: does not handle a non-200 response or a connection error; both
    cases currently raise an unhandled exception instead of a clear,
    well-typed error.
    """
    http_get = http_get or requests.get
    response = http_get(url)
    return response.json()["status"]
