"""Authentication: API key → JWT exchange + in-memory caching.

The SDK accepts a long-lived API key (``mme_live_...``) and handles the
exchange with ``/auth/exchange`` transparently. The resulting JWT is cached
and automatically refreshed on 401 or shortly before its ``exp`` claim.

Callers never see the JWT. They only provide the API key once.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TokenCache:
    """Thread-unsafe in-memory cache for the current JWT.

    Thread-safety is not required because ``httpx.Client`` and
    ``httpx.AsyncClient`` each drive a single TokenCache instance bound
    to their own event loop or thread.
    """

    api_key: str
    _jwt: Optional[str] = field(default=None, repr=False)
    _expires_at: float = 0.0  # unix seconds

    # Refresh this many seconds before the JWT's ``exp`` claim, to avoid a
    # race where the token expires mid-flight.
    REFRESH_SKEW_SECONDS: int = 30

    def set(self, jwt: str) -> None:
        """Store a freshly issued JWT and parse its expiry claim."""
        self._jwt = jwt
        self._expires_at = _parse_jwt_expiry(jwt)

    def invalidate(self) -> None:
        """Drop the cached JWT (e.g., after a 401)."""
        self._jwt = None
        self._expires_at = 0.0

    @property
    def jwt(self) -> Optional[str]:
        """Return the cached JWT if it is still fresh, else ``None``."""
        if self._jwt is None:
            return None
        if time.time() >= self._expires_at - self.REFRESH_SKEW_SECONDS:
            return None
        return self._jwt


def _parse_jwt_expiry(jwt: str) -> float:
    """Return the ``exp`` claim from a JWT as a unix timestamp.

    Silently returns ``0.0`` if the token is malformed or missing ``exp``;
    the caller will then treat the token as already-expired, which forces
    a safe re-exchange on next use.
    """
    try:
        parts = jwt.split(".")
        if len(parts) != 3:
            return 0.0
        # Base64url-decode the payload, pad as needed.
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes)
        exp = payload.get("exp")
        return float(exp) if exp is not None else 0.0
    except (ValueError, KeyError, json.JSONDecodeError):
        return 0.0
