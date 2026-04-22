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

from types import TracebackType
from typing import Any, Optional

import httpx

from railtech_mme.auth import TokenCache
from railtech_mme.exceptions import MMEError
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

    # ------------------------------------------------------------------
    # Context manager protocol — enables ``with MME(...) as mme:``
    # ------------------------------------------------------------------

    def __enter__(self) -> "MME":
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
    ) -> dict[str, Any]:
        """Send an authenticated HTTP request and return the parsed JSON body.

        Implementation outline for Day 1:
          1. Ensure a fresh JWT — call ``_ensure_jwt()`` below.
          2. Build headers: ``Authorization: Bearer <jwt>``, ``Content-Type: application/json``.
          3. If json_body and ``project_id`` is set, inject ``projectId`` for convenience.
          4. Call ``self._http.request(method, path, json=json_body, params=params, headers=...)``.
          5. On 401: invalidate token, retry once.
          6. On 429: parse ``Retry-After`` header, raise :class:`MMERateLimitError`.
          7. On 4xx/5xx: raise the matching exception type.
          8. Return ``response.json()``.
        """
        del method, path, json_body, params
        raise NotImplementedError("TODO Day 1: core HTTP dispatcher")

    def _ensure_jwt(self) -> str:
        """Return a valid JWT, exchanging the API key if needed.

        Implementation outline:
          1. If ``self._tokens.jwt`` is not None, return it.
          2. Otherwise POST ``/auth/exchange`` with ``{"api_key": self._api_key}``.
          3. ``self._tokens.set(response.json()["token"])``.
          4. Return the new JWT.
        """
        raise NotImplementedError("TODO Day 1: exchange mme_live_* for JWT")

    # Silence unused-import warnings during the scaffold phase.
    _unused_refs = (FeedbackRequest, InjectRequest, SaveRequest, MMEError)


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
