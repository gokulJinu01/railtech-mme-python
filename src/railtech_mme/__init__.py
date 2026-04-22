"""Railtech MME — the official Python SDK for the Modular Memory Engine.

Quick start
-----------

    from railtech_mme import MME

    mme = MME(api_key="mme_live_...")
    mme.save("I prefer dark chocolate over milk.")
    pack = mme.inject("What do I like to eat?")
    for item in pack.items:
        print(item.title, item.excerpt)

See https://mme.railtech.io for the dashboard and your API key.
"""

from __future__ import annotations

from railtech_mme.aclient import AsyncMME
from railtech_mme.client import MME
from railtech_mme.exceptions import (
    MMEAuthError,
    MMEBudgetExceeded,
    MMEClientError,
    MMEError,
    MMERateLimitError,
    MMEServerError,
    MMETimeoutError,
)
from railtech_mme.models import (
    Bounds,
    Pack,
    PackItem,
    Rationale,
    SaveResult,
    Score,
    Tag,
)

__version__ = "0.1.0.dev0"

__all__ = [
    # Clients
    "MME",
    "AsyncMME",
    # Models
    "Bounds",
    "MMEAuthError",
    "MMEBudgetExceeded",
    "MMEClientError",
    # Errors
    "MMEError",
    "MMERateLimitError",
    "MMEServerError",
    "MMETimeoutError",
    "Pack",
    "PackItem",
    "Rationale",
    "SaveResult",
    "Score",
    "Tag",
    "__version__",
]
