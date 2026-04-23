"""Async client for the MME HTTP API — mirror of :mod:`railtech_mme.client`.

Example::

    import asyncio
    from railtech_mme import AsyncMME

    async def main():
        async with AsyncMME(api_key="mme_live_...") as mme:
            await mme.save("hello")
            pack = await mme.inject("hello")
            print(pack.items[0].excerpt)

    asyncio.run(main())

The structure of this module is intentionally a 1:1 port of
:mod:`railtech_mme.client`. If you change one, change the other — the test
matrix expects identical semantics on both clients.
"""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Optional, cast

import httpx

from railtech_mme.auth import TokenCache
from railtech_mme.client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    _extract_error_message,
    _parse_retry_after,
    _resolve_api_key,
    _safe_json,
)
from railtech_mme.exceptions import (
    MMEAuthError,
    MMEClientError,
    MMEError,
    MMERateLimitError,
    MMEServerError,
    MMETimeoutError,
)
from railtech_mme.models import (
    InjectFilters,
    Pack,
    PackItem,
    SaveResult,
)


class AsyncMME:
    """Async MME client. See :class:`~railtech_mme.client.MME` for parameter docs."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        project_id: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        resolved_key = _resolve_api_key(api_key)
        self._api_key = resolved_key
        self._base_url = base_url.rstrip("/")
        self._project_id = project_id
        self._timeout = timeout

        self._owned_http_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
        )

        self._tokens = TokenCache(api_key=resolved_key)

        # Populated by the first successful /auth/exchange — see _ensure_jwt.
        self._user_id: Optional[str] = None
        self._org_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AsyncMME:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying async HTTP pool. Safe to call multiple times."""
        if self._owned_http_client:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Public API — signatures mirror the sync client 1:1
    # ------------------------------------------------------------------

    async def save(
        self,
        content: str,
        *,
        tags: Optional[list[str]] = None,
        section: Optional[str] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> SaveResult:
        """Persist a memory block. See :meth:`MME.save`."""
        body: dict[str, Any] = {"content": content}
        if tags is not None:
            body["tags"] = tags
        if section is not None:
            body["section"] = section
        if status is not None:
            body["status"] = status
        if source is not None:
            body["source"] = source
        response = await self._request("POST", "/memory/save", json_body=body)
        return SaveResult(**response)

    async def inject(
        self,
        prompt: str,
        *,
        token_budget: int = 2048,
        limit: Optional[int] = None,
        filters: Optional[InjectFilters] = None,
        project_id: Optional[str] = None,
        debug: bool = False,
    ) -> Pack:
        """Retrieve a memory pack. See :meth:`MME.inject`."""
        scope = await self._tenant_scope(project_override=project_id)
        body: dict[str, Any] = {
            "prompt": prompt,
            "tokenBudget": token_budget,
            "debug": debug,
            **scope,
        }
        if limit is not None:
            body["limit"] = limit
        if filters is not None:
            body["filters"] = filters.model_dump(by_alias=True, exclude_none=True)
        response = await self._request("POST", "/memory/inject", json_body=body)
        return Pack(**response)

    async def feedback(
        self,
        *,
        pack_id: str,
        accepted: bool,
        item_ids: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """Record pack feedback. See :meth:`MME.feedback`."""
        scope = await self._tenant_scope(project_override=project_id)
        body: dict[str, Any] = {
            "packId": pack_id,
            "accepted": accepted,
            "itemIds": item_ids or [],
            "tags": tags or [],
            **scope,
        }
        await self._request("POST", "/memory/feedback", json_body=body)

    async def recent(
        self,
        *,
        limit: int = 20,
        section: Optional[str] = None,
    ) -> list[PackItem]:
        """Return recent memory blocks. See :meth:`MME.recent`."""
        params: dict[str, Any] = {"limit": limit}
        if section is not None:
            params["section"] = section
        response = await self._request("GET", "/memory/recent", params=params)
        raw_items = response.get("results") or []
        return [PackItem(**item) for item in raw_items]

    async def delete(self, memory_id: str) -> None:
        """Delete a memory block. See :meth:`MME.delete`."""
        await self._request("DELETE", f"/memory/{memory_id}")

    async def tags(self) -> list[str]:
        """Return all tags. See :meth:`MME.tags`."""
        response = await self._request("GET", "/tags/all")
        raw_tags = response.get("tags") or []
        return [str(t) for t in raw_tags]

    # ------------------------------------------------------------------
    # Internal helpers — async versions of the sync helpers
    # ------------------------------------------------------------------

    async def _tenant_scope(
        self, *, project_override: Optional[str] = None
    ) -> dict[str, str]:
        """Return ``{orgId, projectId?}`` for endpoints that need it in the body."""
        await self._ensure_jwt()
        if not self._org_id:
            raise MMEAuthError(
                "Server did not return org_id during /auth/exchange; "
                "cannot scope request to a tenant.",
                status_code=500,
            )
        scope: dict[str, str] = {"orgId": self._org_id}
        project = project_override or self._project_id
        if project:
            scope["projectId"] = project
        return scope

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
        _retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """Async version of :meth:`MME._request`. Same contract, same error taxonomy."""
        jwt = await self._ensure_jwt()
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Content-Type": "application/json",
        }

        try:
            response = await self._http.request(
                method,
                path,
                json=json_body,
                params=params,
                headers=headers,
            )
        except httpx.TimeoutException as e:
            raise MMETimeoutError(f"{method} {path} timed out after {self._timeout}s") from e
        except httpx.HTTPError as e:
            raise MMEError(f"Network error on {method} {path}: {e}") from e

        # --- Success path ---------------------------------------------------
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

        # --- Error path -----------------------------------------------------
        body = _safe_json(response)
        message = _extract_error_message(body, response.status_code)

        if response.status_code == 401:
            self._tokens.invalidate()
            if _retry_on_401:
                return await self._request(
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

        raise MMEError(
            f"Unexpected status {response.status_code}: {message}",
            status_code=response.status_code,
            response_body=body,
        )

    async def _ensure_jwt(self) -> str:
        """Async version of :meth:`MME._ensure_jwt`. Same caching, same side effects."""
        cached = self._tokens.jwt
        if cached is not None:
            return cached

        try:
            response = await self._http.post(
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
        user_id = data.get("user_id")
        org_id = data.get("org_id")
        if isinstance(user_id, str):
            self._user_id = user_id
        if isinstance(org_id, str):
            self._org_id = org_id

        return jwt
