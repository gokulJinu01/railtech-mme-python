# railtech-mme

Python SDK for **MME** — the [Modular Memory Engine](https://mme.railtech.io) by Rail Tech.

Tag-graph memory for LLMs. Bounded retrieval. Hard token budgets. Learns from use.

```bash
pip install railtech-mme
```

## Quick start

```python
from railtech_mme import MME

mme = MME(api_key="mme_live_...")          # get one at https://mme.railtech.io

mme.save("I prefer dark chocolate over milk.")
pack = mme.inject("What do I like to eat?")

for item in pack.items:
    print(item.title, item.excerpt, item.score.total)

mme.feedback(pack_id=pack.pack_id, accepted=True)
```

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

## LangChain

```bash
pip install "railtech-mme[langchain]"
```

```python
from railtech_mme import MME
from railtech_mme.langchain import MMESaveTool, MMEInjectTool

mme = MME(api_key="mme_live_...")
tools = [MMESaveTool(mme=mme), MMEInjectTool(mme=mme)]
```

## API surface

| Method | What it does |
|---|---|
| `mme.save(content, *, tags=None, section=None, status=None, source=None)` | Persist a memory block. Returns `SaveResult`. |
| `mme.inject(prompt, *, token_budget=2048, limit=None, filters=None, debug=False)` | Retrieve a token-budgeted `Pack`. |
| `mme.feedback(*, pack_id, accepted, item_ids=None, tags=None)` | Mark a pack as useful or not — trains the edge graph. |
| `mme.recent(*, limit=20, section=None)` | List the most recent memories. |
| `mme.delete(memory_id)` | Remove a memory. |
| `mme.tags()` | List all tags known for the org. |

`AsyncMME` has the same surface with `async def` / `await`.

## Auth

Get your `mme_live_...` API key at **https://mme.railtech.io → API Key**.

The SDK can read it from the `RAILTECH_API_KEY` environment variable:

```bash
export RAILTECH_API_KEY=mme_live_...
```

```python
mme = MME()  # reads from env
```

## Errors

All SDK errors inherit from `MMEError`:

```python
from railtech_mme import MMEError, MMEAuthError, MMERateLimitError

try:
    mme.save("...")
except MMERateLimitError as e:
    time.sleep(e.retry_after or 60)
except MMEAuthError:
    # refresh your key
    ...
except MMEError as e:
    print(e.status_code, e.response_body)
```

## Architecture — what MME does differently

MME does **not** use vector embeddings. It uses a **bounded tag-graph** that learns from pack accept/reject events. Retrieval is:

1. Extract seed tags from the prompt
2. Spread activation across the tag graph (bounded depth, beam width, decay)
3. Score memories (activation + recency + importance + status − diversity penalty)
4. Pack into a hard token budget greedily

Every pack respects the budget exactly. Every retrieval is explainable (seed tags, bounds, activation paths returned in the response). Read the [whitepaper](https://mme.railtech.io/whitepaper) for the full picture.

## License

Apache-2.0
