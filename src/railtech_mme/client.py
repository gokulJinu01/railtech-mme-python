"""Synchronous client for the MME HTTP API.

The :class:`MME` class is the normal entry point for blocking Python code.
For ``async/await`` code, use :class:`~railtech_mme.aclient.AsyncMME` —
same method names, same semantics, same return types.

Example::

    from railtech_mme import MME

    with MME(api_key="mme_live_...") as mme:
        mme.save("I prefer dark chocolate.")
        pack = mme.inject("What do I like?")
        print(pack.items[0].excerpt)

Day-1 scaffold note
-------------------

All network bodies below raise :class:`NotImplementedError`. The method
signatures, docstrings, and return types are final. Fill in each body with
an ``httpx.Client`` call, map the response to the declared Pydantic model,
and map server errors to the appropriate exception class from
:mod:`railtech_mme.exceptions`.

See the identical async implementation in :mod:`railtech_mme.aclient` for
structural symmetry; do not let the two clients drift.
"""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Optional, cast

import httpx

from railtech_mme.auth import TokenCache
from railtech_mme.exceptions import (
    MMEAuthError,
    MMEClientError,
    MMEError,
    MMERateLimitError,
    MMEServerError,
    MMETimeoutError,
)
from railtech_mme.models import (
    FeedbackRequest,
    InjectFilters,
    InjectRequest,
    Pack,
    PackItem,
    SaveRequest,
    SaveResult,
)

DEFAULT_BASE_URL = "https://api.railtech.io"
DEFAULT_TIMEOUT = 15.0  # seconds


class MME:
    """Synchronous MME client.

    Parameters
    ----------
    api_key:
        Your ``mme_live_...`` key. Get one at https://mme.railtech.io.
        Falls back to the ``RAILTECH_API_KEY`` environment variable when
        omitted.
    base_url:
        Override the MME API base URL. Defaults to ``https://api.railtech.io``.
    project_id:
        Default ``projectId`` attached to every request. Can be overridden
        per-call.
    timeout:
        Per-request timeout in seconds. Defaults to 15.
    http_client:
        Inject a preconfigured ``httpx.Client`` if you need custom
        transport, proxy, or retry behaviour. The SDK will not close a
        client it did not create.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        project_id: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        resolved_key = _resolve_api_key(api_key)
        self._api_key = resolved_key
        self._base_url = base_url.rstrip("/")
        self._project_id = project_id
        self._timeout = timeout

        self._owned_http_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
        )

        self._tokens = TokenCache(api_key=resolved_key)

        # Populated by the first successful /auth/exchange; required as
        # ``orgId`` in the body of /memory/inject and /memory/feedback.
        self._user_id: Optional[str] = None
        self._org_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Context manager protocol — enables ``with MME(...) as mme:``
    # ------------------------------------------------------------------

    def __enter__(self) -> MME:
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool.

        Safe to call multiple times. No-op if an external ``http_client``
        was injected via the constructor.
        """
        if self._owned_http_client:
            self._http.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        content: str,
        *,
        tags: Optional[list[str]] = None,
        section: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> SaveResult:
        """Persist a memory block.

        Parameters
        ----------
        content:
            The text to remember. Required.
        tags:
            Optional pre-assigned tags. If omitted, the server's tagmaker
            will generate them automatically from ``content``.
        section:
            Logical grouping inside the user's memory (e.g., ``"work"``).
        status:
            One of ``draft | submitted | completed``. Affects scoring.
        source:
            Optional free-form source identifier for provenance.

        Returns
        -------
        :class:`SaveResult` with the new block's ``id``.

        Raises
        ------
        MMEAuthError, MMERateLimitError, MMEServerError
        """
        del content, tags, section, status, source  # consumed in body below
        raise NotImplementedError(
            "TODO Day 1: POST /memory/save — serialize SaveRequest, call _request, "
            "parse SaveResult. See Go handler at "
            "mme-tagging-service/internal/memory/handlers.go (SaveBlock)."
        )

    def inject(
        self,
        prompt: str,
        *,
        token_budget: int = 2048,
        limit: Optional[int] = None,
        filters: Optional[InjectFilters] = None,
        project_id: Optional[str] = None,
        debug: bool = False,
    ) -> Pack:
        """Retrieve a token-budgeted memory pack for ``prompt``.

        Parameters
        ----------
        prompt:
            The user's query. Seed tags are extracted from this text.
        token_budget:
            Hard cap on total tokens in the returned pack. Default 2048.
        limit:
            Max number of items to return. Default is server-side ~20.
        filters:
            Optional filters (``section``, ``status``, ``since``).
        project_id:
            Override the client's default project. Pass ``None`` to use
            the constructor default.
        debug:
            When ``True``, the response includes a ``debug`` field with
            activation paths, dropped items, and diversity data.

        Returns
        -------
        :class:`Pack` whose ``items`` collectively fit within ``token_budget``.
        """
        del prompt, token_budget, limit, filters, project_id, debug
        raise NotImplementedError(
            "TODO Day 1: POST /memory/inject — build InjectRequest from kwargs "
            "(include orgId from JWT), call _request, parse Pack. "
            "See Go handler in mme-tagging-service/internal/memory/inject.go."
        )

    def feedback(
        self,
        *,
        pack_id: str,
        accepted: bool,
        item_ids: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """Record whether a previously-returned pack was accepted.

        The server uses this signal to tune tag-edge weights via EMA
        learning. Calling feedback is optional but strongly recommended —
        without it, the graph cannot improve from real outcomes.

        Parameters
        ----------
        pack_id:
            The ``packId`` from a previous :meth:`inject` response.
        accepted:
            ``True`` if the pack helped, ``False`` if it did not.
        item_ids:
            Subset of pack items that were actually useful (optional).
        tags:
            Tags the caller found salient (optional).
        project_id:
            Override the client's default project.
        """
        del pack_id, accepted, item_ids, tags, project_id
        raise NotImplementedError(
            "TODO Day 1: POST /memory/feedback — build FeedbackRequest, call _request, "
            "discard body. See Go handler in internal/memory/events.go (HandlePackEvent)."
        )

    def recent(
        self,
        *,
        limit: int = 20,
        section: Optional[str] = None,
    ) -> list[PackItem]:
        """Return the most recent memory blocks for the authenticated user."""
        del limit, section
        raise NotImplementedError("TODO Day 1: GET /memory/recent")

    def delete(self, memory_id: str) -> None:
        """Delete a single memory block by id."""
        del memory_id
        raise NotImplementedError("TODO Day 1: DELETE /memory/:id")

    def tags(self) -> list[str]:
        """Return all tags known for the authenticated org."""
        raise NotImplementedError("TODO Day 1: GET /tags/all")

    # ------------------------------------------------------------------
    # Internal helpers — fill in on Day 1
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        _retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """Send an authenticated request and return the parsed JSON body.

        Handles the full error taxonomy:

        * **401** → invalidate cached JWT, retry once; if still 401, raise
          :class:`MMEAuthError`.
        * **403** → :class:`MMEAuthError` (no retry; this is a permission
          problem, not a stale token).
        * **429** → :class:`MMERateLimitError` with ``retry_after`` parsed
          from the ``Retry-After`` header (RFC 6585).
        * **4xx** (other) → :class:`MMEClientError`.
        * **5xx** → :class:`MMEServerError`.
        * Timeout → :class:`MMETimeoutError`.
        * Any other network failure → :class:`MMEError`.

        A **2xx** response with an empty body (e.g., 204 No Content) returns
        an empty dict.
        """
        jwt = self._ensure_jwt()
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
        }

        try:
            response = self._http.request(
                method,
                path,
                json=json_body,
                params=params,
                headers=headers,
            )
        except httpx.TimeoutException as e:
            raise MMETimeoutError(f"{method} {path} timed out after {self._timeout}s") from e
        except httpx.HTTPError as e:  # network failures, DNS, etc.
            raise MMEError(f"Network error on {method} {path}: {e}") from e

        # --- Success path ----------------------------------------------------
        if response.is_success:
            if response.status_code == 204 or not response.content:
                return {}
            try:
                parsed: Any = response.json()
            except (ValueError, json.JSONDecodeError) as e:
                raise MMEServerError(
                    f"Server returned non-JSON on {response.status_code}: {e}",
                    status_code=response.status_code,
                ) from e
            if not isinstance(parsed, dict):
                raise MMEServerError(
                    f"Expected JSON object from {method} {path}, "
                    f"got {type(parsed).__name__}",
                    status_code=response.status_code,
                    response_body={"data": parsed},
                )
            return cast("dict[str, Any]", parsed)

        # --- Error path ------------------------------------------------------
        body = _safe_json(response)
        message = _extract_error_message(body, response.status_code)

        if response.status_code == 401:
            self._tokens.invalidate()
            if _retry_on_401:
                return self._request(
                    method,
                    path,
                    json_body=json_body,
                    params=params,
                    _retry_on_401=False,
                )
            raise MMEAuthError(message, status_code=401, response_body=body)

        if response.status_code == 403:
            raise MMEAuthError(message, status_code=403, response_body=body)

        if response.status_code == 429:
            raise MMERateLimitError(
                message,
                retry_after=_parse_retry_after(response),
                status_code=429,
                response_body=body,
            )

        if 400 <= response.status_code < 500:
            raise MMEClientError(
                message,
                status_code=response.status_code,
                response_body=body,
            )

        if response.status_code >= 500:
            raise MMEServerError(
                message,
                status_code=response.status_code,
                response_body=body,
            )

        # Should be unreachable — every status code is handled above.
        raise MMEError(
            f"Unexpected status {response.status_code}: {message}",
            status_code=response.status_code,
            response_body=body,
        )

    def _ensure_jwt(self) -> str:
        """Return a valid JWT, exchanging the API key if needed.

        Side effect: on first successful exchange, also records ``_user_id``
        and ``_org_id`` on the client so subsequent requests can include
        ``orgId`` in bodies that require it.
        """
        cached = self._tokens.jwt
        if cached is not None:
            return cached

        # Exchange the API key — note: this call is unauthenticated, so we
        # do NOT go through ``_request`` (which would recurse).
        try:
            response = self._http.post(
                "/auth/exchange",
                json={"apiKey": self._api_key},
                headers={"Content-Type": "application/json"},
            )
        except httpx.TimeoutException as e:
            raise MMETimeoutError(
                f"/auth/exchange timed out after {self._timeout}s"
            ) from e
        except httpx.HTTPError as e:
            raise MMEError(f"Network error on /auth/exchange: {e}") from e

        if response.status_code == 401:
            body = _safe_json(response)
            raise MMEAuthError(
                _extract_error_message(body, 401)
                or "Invalid or inactive API key. "
                "Get a new one at https://mme.railtech.io.",
                status_code=401,
                response_body=body,
            )
        if response.status_code == 429:
            body = _safe_json(response)
            raise MMERateLimitError(
                _extract_error_message(body, 429) or "Too many exchange attempts",
                retry_after=_parse_retry_after(response),
                status_code=429,
                response_body=body,
            )
        if not response.is_success:
            body = _safe_json(response)
            raise MMEServerError(
                _extract_error_message(body, response.status_code)
                or f"Auth exchange failed: {response.status_code}",
                status_code=response.status_code,
                response_body=body,
            )

        try:
            data = cast("dict[str, Any]", response.json())
        except (ValueError, json.JSONDecodeError) as e:
            raise MMEServerError(
                f"/auth/exchange returned non-JSON: {e}",
                status_code=response.status_code,
            ) from e

        jwt = data.get("token")
        if not isinstance(jwt, str) or not jwt:
            raise MMEServerError(
                "/auth/exchange succeeded but returned no 'token' field",
                status_code=response.status_code,
                response_body=data,
            )

        self._tokens.set(jwt)
        # Capture identifiers for body injection on inject/feedback.
        user_id = data.get("user_id")
        org_id = data.get("org_id")
        if isinstance(user_id, str):
            self._user_id = user_id
        if isinstance(org_id, str):
            self._org_id = org_id

        return jwt

    # Silence unused-import warnings during the scaffold phase (save/inject/
    # feedback bodies still stubbed; remove these once those are filled in).
    _unused_refs = (FeedbackRequest, InjectFilters, InjectRequest, PackItem, SaveRequest)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    """Best-effort JSON parse of an error response body.

    Returns an empty dict if the body is not valid JSON or not an object.
    Never raises — error handling should not itself fail.
    """
    try:
        parsed = response.json()
    except (ValueError, json.JSONDecodeError):
        return {}
    if isinstance(parsed, dict):
        return cast("dict[str, Any]", parsed)
    return {"data": parsed}


def _extract_error_message(body: dict[str, Any], status_code: int) -> str:
    """Extract a human-readable message from an MME error body.

    MME errors are shaped ``{"error": "...", "code": "..."}``. Fall back to
    the status code if no ``error`` field is present.
    """
    error = body.get("error")
    if isinstance(error, str) and error:
        return error
    return f"HTTP {status_code}"


def _parse_retry_after(response: httpx.Response) -> Optional[int]:
    """Parse the ``Retry-After`` header (RFC 6585) in seconds.

    MME's Traefik middleware emits the integer-seconds form. The HTTP-date
    form is allowed by the spec but not produced by our backend, so we
    accept only the integer form and return ``None`` otherwise.
    """
    header = response.headers.get("Retry-After") or response.headers.get("retry-after")
    if header is None:
        return None
    try:
        return int(header)
    except ValueError:
        return None


def _resolve_api_key(explicit: Optional[str]) -> str:
    """Resolve the API key from the explicit arg or environment."""
    import os

    key = explicit or os.environ.get("RAILTECH_API_KEY")
    if not key:
        raise ValueError(
            "No API key provided. Pass api_key=... or set the "
            "RAILTECH_API_KEY environment variable. "
            "Get a key at https://mme.railtech.io."
        )
    return key
