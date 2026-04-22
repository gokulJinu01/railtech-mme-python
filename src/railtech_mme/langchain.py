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

from typing import Any, Optional

try:
    from langchain_core.tools import BaseTool  # type: ignore[import-not-found, unused-ignore]

    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False

    class BaseTool:  # type: ignore[no-redef]
        """Fallback stub used only when langchain-core is not installed."""


from railtech_mme.client import MME


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
        """TODO Day 2: call self.mme.save(content) and return result.id."""
        del content
        raise NotImplementedError("TODO Day 2: wire to MME.save")

    async def _arun(self, content: str) -> str:
        """TODO Day 2: use AsyncMME when available."""
        del content
        raise NotImplementedError("TODO Day 2: wire to AsyncMME.save")


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
        """TODO Day 2: call self.mme.inject(query) and format items."""
        del query
        raise NotImplementedError("TODO Day 2: wire to MME.inject")

    async def _arun(self, query: str) -> str:
        """TODO Day 2: async variant."""
        del query
        raise NotImplementedError("TODO Day 2: wire to AsyncMME.inject")


__all__ = ["MMESaveTool", "MMEInjectTool"]
