# Memory for LLMs without a vector database

*A launch post for `railtech-mme` 0.1.0 — the official Python SDK for MME.*

---

Every LLM call starts the same way: empty context. The model knows nothing about you, your project, or the conversation you had with it five minutes ago. The standard fix is to bolt on a vector database, embed everything, and hope the cosine similarity points at something useful. It usually doesn't.

We've been building a different shape of memory for the last six months. Today we're shipping the Python SDK that talks to it.

## What MME is

MME — the **Modular Memory Engine** — is a hosted memory layer for LLM applications. You save facts as they happen. You ask for relevant ones at prompt time. You get back a *pack* that fits inside a hard token budget, sorted by relevance, with a full explanation of why each item made it in.

What makes it different is the retrieval algorithm. There are no embeddings.

Instead, every memory is tagged — automatically, structurally — with labels that describe what it's about, what section of your life or project it belongs to, who said it, when. Retrieval works by:

1. Pulling tags out of the incoming prompt
2. Spreading activation across the tag graph (bounded depth, beam width, decay — so it terminates)
3. Scoring memories against the activated tags plus recency, importance, and status
4. Greedily packing the top-scoring ones into your token budget

Every step is explainable. The pack you get back tells you which seed tags fired, which graph paths were traversed, and what each item's score breakdown was. No black box, no "the embedding said so."

The graph also learns. Every pack you accept or reject is fed back into the edge weights, so retrieval gets sharper over time without any retraining.

## What the SDK looks like

```bash
pip install railtech-mme
```

```python
from railtech_mme import MME

mme = MME(api_key="mme_live_...")          # get one at https://mme.railtech.io

mme.save("I prefer dark chocolate over milk.")
mme.save("I'm allergic to peanuts.")

pack = mme.inject("What should we order for dessert?")
for item in pack.items:
    print(f"- {item.title}: {item.excerpt}")

mme.feedback(pack_id=pack.pack_id, accepted=True)
```

That's the whole loop. Save what matters as it happens. Inject when you need it. Tell MME whether the pack was useful. The next pack will be better.

There's a fully-async client (`AsyncMME`) with the same surface, and a LangChain integration that drops both `save` and `inject` in as tools any agent can call:

```python
from railtech_mme import MME
from railtech_mme.langchain import MMESaveTool, MMEInjectTool

mme = MME()
tools = [MMESaveTool(mme=mme), MMEInjectTool(mme=mme)]
# hand `tools` to your LangChain or LangGraph agent
```

## What it's good for

The pattern we keep seeing:

- **Long-running agents** that need to remember user preferences, decisions, constraints across sessions without re-uploading the world every turn.
- **Coding assistants** that need to track which files matter to *this* project, what the user already explained about the codebase, what was decided in yesterday's chat.
- **Customer support copilots** where each conversation should benefit from every previous one without ballooning the context window.

The common thread is bounded budgets. Vector RAG over a year of context is expensive and noisy. MME treats the budget as a hard constraint and the relevance as a graph problem instead of a similarity problem.

## What's in 0.1.0

- Sync and async clients with full method parity
- Pydantic models for everything — typed end to end
- A real exception taxonomy with retry-after, status codes, and parsed error bodies
- JWT auth with caching and one-shot refresh on 401
- LangChain `BaseTool` adapters under the `[langchain]` extra
- 88% branch coverage, mypy `--strict` clean
- CI on Python 3.9 through 3.12

The SDK is Apache-2.0 and lives at [github.com/gokulJinu01/railtech-mme-python](https://github.com/gokulJinu01/railtech-mme-python).

## What's next

The Go and TypeScript SDKs are next, sharing the same exception taxonomy and model shapes. After that: a streaming `inject` for low-latency agent loops, server-side embeddings for hybrid retrieval where it actually helps, and a self-hosted distribution for teams that need to keep memory on-prem.

If you're building anything that needs an LLM to remember between calls, [grab a free API key](https://mme.railtech.io) and try it. The free tier is generous enough to run a real agent on. We'd love to hear what breaks.

— Goku Jinu, founder of Rail Tech
