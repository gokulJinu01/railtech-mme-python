# railtech-mme

[![PyPI version](https://img.shields.io/pypi/v/railtech-mme.svg)](https://pypi.org/project/railtech-mme/)
[![CI](https://github.com/gokulJinu01/railtech-mme-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gokulJinu01/railtech-mme-python/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/railtech-mme.svg)](https://pypi.org/project/railtech-mme/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Python SDK for **MME** — the [Modular Memory Engine](https://mme.railtech.io) by Rail Tech.

Tag-graph memory for LLMs. Bounded retrieval. Hard token budgets. Learns from use. No vector DB.

```bash
pip install railtech-mme
```

Requires Python 3.9+.

## Quick start

```python
from railtech_mme import MME

mme = MME(api_key="mme_live_...")          # get one at https://mme.railtech.io

# Save a few facts — MME tags them automatically
mme.save("I prefer dark chocolate over milk chocolate.")
mme.save("I'm allergic to peanuts.")
mme.save("My favorite cuisine is Thai.")

# Recall them later — tag-graph activation matches keywords in the prompt
pack = mme.inject("What are my food preferences and allergies?", token_budget=1024)

for item in pack.items:
    print(f"- {item.title}: {item.excerpt}")

mme.feedback(pack_id=pack.pack_id, accepted=True)
```

That's the whole loop: **save** facts as they happen, **inject** them at prompt time, **feedback** to improve future packs.

> **Tip on prompt phrasing.** MME's retrieval is tag-graph-based, not embedding-based: the prompt's keywords seed propagation across the tag graph. Prompts that share concrete words with your saved facts (`food`, `chocolate`, `allergies`) retrieve reliably even on a brand-new account; abstract paraphrases (`dietary preferences`) only start working after the graph has built up enough edges to bridge the gap. This is by design — it's why MME stays explainable and bounded.

## Async

```python
import asyncio
from railtech_mme import AsyncMME

async def main():
    async with AsyncMME(api_key="mme_live_...") as mme:
        await mme.save("hello")
        pack = await mme.inject("hello")
        print(pack.items[0].excerpt)

asyncio.run(main())
```

`AsyncMME` is a 1:1 mirror of `MME`. Same methods, same exceptions, same return types.

## LangChain

```bash
pip install "railtech-mme[langchain]"
```

```python
from railtech_mme import MME
from railtech_mme.langchain import MMESaveTool, MMEInjectTool

mme = MME(api_key="mme_live_...")
tools = [MMESaveTool(mme=mme), MMEInjectTool(mme=mme)]
# hand `tools` to your agent — see examples/langchain_agent.py for a runnable demo
```

The tools are LangChain `BaseTool` subclasses, so they drop into any agent that accepts tools (LangChain, LangGraph, AutoGen wrappers, etc.).

## API surface

| Method | What it does |
|---|---|
| `mme.save(content, *, tags=None, section=None, status=None, source=None)` | Persist a memory block. Returns `SaveResult`. |
| `mme.inject(prompt, *, token_budget=2048, limit=None, filters=None, debug=False)` | Retrieve a token-budgeted `Pack`. |
| `mme.feedback(*, pack_id, accepted, item_ids=None, tags=None)` | Mark a pack as useful or not — trains the edge graph. |
| `mme.recent(*, limit=20, section=None)` | List the most recent memories as raw `MemoryBlock` objects (full `content` and structured `tags`). |
| `mme.delete(memory_id)` | Remove a memory. |
| `mme.tags()` | List all tags known for the org. |

`AsyncMME` exposes the same surface with `async def` / `await`.

### Filters

Narrow a retrieval to a section, a status, or a time window:

```python
import datetime as dt
from railtech_mme import MME, InjectFilters

mme = MME()
pack = mme.inject(
    "what shipped this sprint?",
    filters=InjectFilters(
        section="work",
        since=dt.datetime(2026, 4, 1, tzinfo=dt.timezone.utc),
    ),
)
```

## Auth

Get your `mme_live_...` API key at **https://mme.railtech.io → API Key**.

The SDK reads it from the `RAILTECH_API_KEY` environment variable if you don't pass it explicitly:

```bash
export RAILTECH_API_KEY=mme_live_...
```

```python
from railtech_mme import MME
mme = MME()  # reads from env
```

The SDK exchanges your API key for a short-lived JWT on first use and caches it for the life of the client. Token refresh is automatic on 401.

## Errors

All SDK errors inherit from `MMEError`:

```python
import time
from railtech_mme import MME, MMEError, MMEAuthError, MMERateLimitError

mme = MME()
try:
    mme.save("...")
except MMERateLimitError as e:
    time.sleep(e.retry_after or 60)
except MMEAuthError:
    # API key is invalid or revoked — get a new one
    raise
except MMEError as e:
    print(e.status_code, e.response_body)
```

The full taxonomy: `MMEError` → `MMEAuthError`, `MMEClientError`, `MMERateLimitError`, `MMEServerError`, `MMETimeoutError`, `MMEBudgetExceeded`.

## Architecture — what MME does differently

MME does **not** use vector embeddings. It uses a **bounded tag-graph** that learns from pack accept/reject events. Retrieval is:

1. Extract seed tags from the prompt
2. Spread activation across the tag graph (bounded depth, beam width, decay)
3. Score memories (activation + recency + importance + status − diversity penalty)
4. Pack into a hard token budget greedily

Every pack respects the budget exactly. Every retrieval is explainable — seed tags, bounds, and activation paths come back in the response. Read the [whitepaper](https://mme.railtech.io) for the full picture.

## Examples

Runnable scripts in [`examples/`](examples/):

- [`basic.py`](examples/basic.py) — sync save / inject / feedback
- [`async_basic.py`](examples/async_basic.py) — async equivalent
- [`langchain_agent.py`](examples/langchain_agent.py) — minimal ReAct agent with both MME tools

Each one reads `RAILTECH_API_KEY` from the environment.

## Links

- **Dashboard & API key:** https://mme.railtech.io
- **Issues:** https://github.com/gokulJinu01/railtech-mme-python/issues
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

## License

Apache-2.0
