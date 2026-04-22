"""Exception hierarchy for the Railtech MME SDK."""

from __future__ import annotations

from typing import Any, Optional


class MMEError(Exception):
    """Base class for all MME SDK errors.

    All exceptions raised by this SDK inherit from :class:`MMEError`, so
    callers can catch one exception type to handle any SDK failure.

    Attributes
    ----------
    message:
        Human-readable description of what went wrong.
    status_code:
        HTTP status code when the error originated from an API response,
        otherwise ``None`` (e.g., network errors).
    response_body:
        Parsed JSON body of the error response, if available.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        response_body: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body


class MMEAuthError(MMEError):
    """Authentication or authorization failed (HTTP 401 or 403).

    Common causes: invalid API key, expired JWT that could not be refreshed,
    missing or mismatched ``orgId`` in the request body, or an account
    without permission for the endpoint.
    """


class MMERateLimitError(MMEError):
    """Server rejected the request because the user exceeded rate limits (HTTP 429).

    Attributes
    ----------
    retry_after:
        Number of seconds the client should wait before retrying, taken from
        the ``Retry-After`` response header (RFC 6585). May be ``None`` if
        the server did not send the header.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after: Optional[int] = None,
        status_code: Optional[int] = 429,
        response_body: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, status_code=status_code, response_body=response_body)
        self.retry_after = retry_after


class MMEBudgetExceeded(MMEError):
    """The request would exceed a token, storage, or quota budget."""


class MMEClientError(MMEError):
    """4xx response that is not specifically modelled by another error class."""


class MMEServerError(MMEError):
    """5xx response from the MME backend."""


class MMETimeoutError(MMEError):
    """The HTTP request did not complete before the configured timeout."""
