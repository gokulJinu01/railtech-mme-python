"""Tests for the LangChain tools wired in :mod:`railtech_mme.langchain`.

These use a ``unittest.mock.Mock`` for the ``MME`` instance so each tool can
be exercised in isolation, without spinning up an HTTPX mock cascade. The
HTTP layer is already covered in :mod:`tests.test_client`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from unittest.mock import Mock

import pytest

from railtech_mme import MME, Pack, PackItem, SaveResult
from railtech_mme.langchain import MMEInjectTool, MMESaveTool, _format_pack


@pytest.fixture
def fake_mme() -> Iterator[Mock]:
    """A Mock standing in for a real MME — no HTTP, just stubbed return values."""
    mme = Mock(spec=MME)
    mme.save.return_value = SaveResult(id="mem-fake-1", status="created")
    mme.inject.return_value = Pack(
        packId="pack-fake",
        seedTags=["chocolate"],
        tokenBudget=2048,
        totalTokens=64,
        items=[
            PackItem(
                id="mem-1",
                title="Preference",
                tags=["food"],
                excerpt="I like dark chocolate.",
                tokenCost=32,
            ),
            PackItem(
                id="mem-2",
                title="Allergy",
                tags=["health"],
                excerpt="Allergic to peanuts.",
                tokenCost=32,
            ),
        ],
    )
    yield mme


# ---------------------------------------------------------------------------
# MMESaveTool
# ---------------------------------------------------------------------------


def test_save_tool_run_returns_new_memory_id(fake_mme: Mock) -> None:
    tool = MMESaveTool(mme=fake_mme)
    result = tool._run("I like dark chocolate.")

    assert result == "mem-fake-1"
    fake_mme.save.assert_called_once_with("I like dark chocolate.")


def test_save_tool_arun_delegates_to_sync(fake_mme: Mock) -> None:
    """``_arun`` should hop through asyncio.to_thread and return the same id."""
    tool = MMESaveTool(mme=fake_mme)
    result = asyncio.run(tool._arun("hello async"))

    assert result == "mem-fake-1"
    fake_mme.save.assert_called_once_with("hello async")


# ---------------------------------------------------------------------------
# MMEInjectTool
# ---------------------------------------------------------------------------


def test_inject_tool_run_formats_items_one_per_line(fake_mme: Mock) -> None:
    tool = MMEInjectTool(mme=fake_mme)
    result = tool._run("what do I like to eat?")

    assert result == (
        "- Preference: I like dark chocolate.\n"
        "- Allergy: Allergic to peanuts."
    )
    fake_mme.inject.assert_called_once_with("what do I like to eat?")


def test_inject_tool_arun_delegates_to_sync(fake_mme: Mock) -> None:
    tool = MMEInjectTool(mme=fake_mme)
    result = asyncio.run(tool._arun("query"))

    assert "Preference" in result
    assert "Allergy" in result


def test_inject_tool_run_empty_pack_returns_friendly_string() -> None:
    """An empty pack should render a deterministic message, not an empty string."""
    mme = Mock(spec=MME)
    mme.inject.return_value = Pack(
        packId="empty",
        seedTags=[],
        tokenBudget=2048,
        totalTokens=0,
        items=[],
    )

    tool = MMEInjectTool(mme=mme)
    result = tool._run("query with no matches")

    assert result == "(no relevant memories found)"


# ---------------------------------------------------------------------------
# _format_pack — the rendering helper
# ---------------------------------------------------------------------------


def test_format_pack_handles_item_with_no_excerpt() -> None:
    """If excerpt is empty, render just the title — never a dangling colon."""
    pack = Pack(
        packId="p",
        seedTags=[],
        tokenBudget=2048,
        totalTokens=0,
        items=[
            PackItem(id="1", title="Title only", tags=[], excerpt="", tokenCost=10),
        ],
    )

    assert _format_pack(pack) == "- Title only"


# ---------------------------------------------------------------------------
# Defensive paths
# ---------------------------------------------------------------------------


def test_save_tool_without_mme_raises_runtime_error() -> None:
    """If somebody constructs a tool then nulls out ``mme``, _run must complain clearly."""
    fake = Mock(spec=MME)
    fake.save.return_value = SaveResult(id="x")
    tool = MMESaveTool(mme=fake)
    tool.mme = None  # simulating an internal misconfiguration

    with pytest.raises(RuntimeError, match="MMESaveTool requires an MME"):
        tool._run("hi")


def test_inject_tool_without_mme_raises_runtime_error() -> None:
    fake = Mock(spec=MME)
    tool = MMEInjectTool(mme=fake)
    tool.mme = None

    with pytest.raises(RuntimeError, match="MMEInjectTool requires an MME"):
        tool._run("hi")
