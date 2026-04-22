"""Pydantic models for request/response shapes exposed by the MME HTTP API.

These mirror the Go structs in ``mme-tagging-service/internal/memory/``:
:class:`MemoryBlock`, :class:`InjectRequest`, :class:`InjectResponse`,
:class:`PackEvent`, and their nested types.

The SDK accepts and returns these models so callers get full type safety
and IDE autocomplete, and so any drift between server and SDK surfaces
as a validation error rather than a silent corruption.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class _MMEModel(BaseModel):
    """Base model: allow extra fields so server additions don't break clients."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Tag(_MMEModel):
    """A structured tag attached to a memory block."""

    label: str
    section: Optional[str] = None
    origin: Optional[str] = None  # agent | system | user | unknown
    scope: Optional[str] = None  # local | shared | global
    type: Optional[str] = None
    confidence: Optional[float] = None
    links: Optional[list[str]] = None
    usage_count: Optional[int] = Field(default=None, alias="usageCount")
    last_used: Optional[datetime] = Field(default=None, alias="lastUsed")


class Score(_MMEModel):
    """Per-item score breakdown returned by ``/memory/inject``.

    The total is: ``β1·activation + β2·recency + β3·importance + β4·statusBonus − diversityPenalty``
    with defaults ``β1=1.0, β2=0.2, β3=0.25, β4=0.25``.
    """

    activation: float = 0.0
    recency: float = 0.0
    importance: float = 0.0
    status_bonus: float = Field(default=0.0, alias="statusBonus")
    diversity_penalty: float = Field(default=0.0, alias="diversityPenalty")
    total: float = 0.0


class PackItem(_MMEModel):
    """One memory block as it appears inside an inject pack."""

    id: str
    title: str
    tags: list[str] = Field(default_factory=list)
    excerpt: str = ""
    token_cost: int = Field(default=0, alias="tokenCost")
    score: Optional[Score] = None


class Bounds(_MMEModel):
    """The bounded-propagation parameters that produced this pack."""

    M: int = 32
    D: int = 2
    B: int = 128
    alpha: float = 0.85
    theta: float = 0.05


class RationalePath(_MMEModel):
    """One edge traversed by bounded propagation during retrieval."""

    from_: str = Field(alias="from")
    to: str
    weight: float = 0.0
    depth: int = 0


class Rationale(_MMEModel):
    """Why the pack looks the way it does — traces and human-readable notes."""

    paths: list[RationalePath] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class Pack(_MMEModel):
    """Response from ``POST /memory/inject``."""

    pack_id: str = Field(alias="packId")
    seed_tags: list[str] = Field(default_factory=list, alias="seedTags")
    bounds: Optional[Bounds] = None
    filters: Optional[dict[str, Any]] = None
    token_budget: int = Field(default=2048, alias="tokenBudget")
    total_tokens: int = Field(default=0, alias="totalTokens")
    items: list[PackItem] = Field(default_factory=list)
    rationale: Optional[Rationale] = None
    debug: Optional[dict[str, Any]] = None


class SaveResult(_MMEModel):
    """Response from ``POST /memory/save``."""

    id: str
    status: Optional[str] = None
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Request models — the SDK constructs these from keyword args; callers rarely
# touch them directly, but they are exported for advanced use cases.
# ---------------------------------------------------------------------------


class SaveRequest(_MMEModel):
    """Body for ``POST /memory/save``."""

    content: str
    tags: Optional[list[Tag]] = None
    section: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None


class InjectFilters(_MMEModel):
    """Optional filters on ``POST /memory/inject``."""

    section: Optional[str] = None
    status: Optional[str] = None
    since: Optional[datetime] = None


class InjectRequest(_MMEModel):
    """Body for ``POST /memory/inject``."""

    org_id: str = Field(alias="orgId")
    project_id: Optional[str] = Field(default=None, alias="projectId")
    prompt: str
    limit: Optional[int] = None
    filters: Optional[InjectFilters] = None
    token_budget: Optional[int] = Field(default=None, alias="tokenBudget")
    debug: bool = False


class FeedbackRequest(_MMEModel):
    """Body for ``POST /memory/feedback``."""

    org_id: str = Field(alias="orgId")
    project_id: Optional[str] = Field(default=None, alias="projectId")
    pack_id: str = Field(alias="packId")
    accepted: bool
    tags: list[str] = Field(default_factory=list)
    item_ids: list[str] = Field(default_factory=list, alias="itemIds")
    ts: Optional[int] = None
