"""LangChain integration for Railtech MME.

Install with::

    pip install "railtech-mme[langchain]"

Usage::

    from langchain.agents import initialize_agent
    from railtech_mme import MME
    from railtech_mme.langchain import MMESaveTool, MMEInjectTool

    mme = MME(api_key="mme_live_...")
    tools = [MMESaveTool(mme=mme), MMEInjectTool(mme=mme)]

    agent = initialize_agent(
        tools,
        llm,
        agent="chat-conversational-react-description",
    )

Implementation note
-------------------

This module imports from ``langchain_core`` lazily — it raises
:class:`ImportError` with a clear message if the ``langchain`` extra is not
installed, so users who never touch LangChain pay zero import cost.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

try:
    from langchain_core.tools import BaseTool  # type: ignore[import-not-found, unused-ignore]

    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False

    class BaseTool:  # type: ignore[no-redef]
        """Fallback stub used only when langchain-core is not installed."""


from railtech_mme.client import MME
from railtech_mme.models import Pack


def _format_pack(pack: Pack) -> str:
    """Render an inject pack as a plain-text block for an LLM prompt.

    One memory per line: ``- {title}: {excerpt}``. Falls back to a friendly
    "no relevant memories" line when the pack is empty so the agent gets a
    deterministic signal instead of an empty string.
    """
    if not pack.items:
        return "(no relevant memories found)"
    lines: list[str] = []
    for item in pack.items:
        title = (item.title or "memory").strip()
        excerpt = (item.excerpt or "").strip()
        lines.append(f"- {title}: {excerpt}" if excerpt else f"- {title}")
    return "\n".join(lines)


def _require_langchain() -> None:
    if not _LANGCHAIN_AVAILABLE:
        raise ImportError(
            "LangChain is required for this feature. "
            "Install it with: pip install 'railtech-mme[langchain]'"
        )


class MMESaveTool(BaseTool):  # type: ignore[misc, unused-ignore]
    """LangChain tool that saves text to MME as a memory block."""

    name: str = "mme_save"
    description: str = (
        "Persist a fact, preference, or observation into the user's MME memory. "
        "Input: the text to remember. Output: the new memory's id."
    )

    mme: Optional[MME] = None

    def __init__(self, *, mme: MME, **kwargs: Any) -> None:
        _require_langchain()
        super().__init__(**kwargs)
        self.mme = mme

    def _run(self, content: str) -> str:
        """Persist ``content`` and return the new memory id."""
        if self.mme is None:
            raise RuntimeError("MMESaveTool requires an MME client (mme=...)")
        result = self.mme.save(content)
        return result.id

    async def _arun(self, content: str) -> str:
        """Async variant — runs the sync client in a worker thread.

        We deliberately reuse the sync :class:`MME` client (rather than
        requiring users to construct an :class:`AsyncMME` separately) so a
        single tool instance works in both sync and async agents. Switch to a
        dedicated :class:`AsyncMME` later if event-loop blocking becomes a
        real concern under load.
        """
        return await asyncio.to_thread(self._run, content)


class MMEInjectTool(BaseTool):  # type: ignore[misc, unused-ignore]
    """LangChain tool that retrieves a memory pack for a prompt."""

    name: str = "mme_inject"
    description: str = (
        "Retrieve relevant memories for a prompt. "
        "Input: a natural-language query. Output: formatted pack of relevant memories."
    )

    mme: Optional[MME] = None

    def __init__(self, *, mme: MME, **kwargs: Any) -> None:
        _require_langchain()
        super().__init__(**kwargs)
        self.mme = mme

    def _run(self, query: str) -> str:
        """Inject memories for ``query`` and return a plain-text formatted pack."""
        if self.mme is None:
            raise RuntimeError("MMEInjectTool requires an MME client (mme=...)")
        pack = self.mme.inject(query)
        return _format_pack(pack)

    async def _arun(self, query: str) -> str:
        """Async variant — runs the sync client in a worker thread."""
        return await asyncio.to_thread(self._run, query)


__all__ = ["MMEInjectTool", "MMESaveTool"]
