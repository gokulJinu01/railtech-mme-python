"""Async end-to-end example: save, inject, feedback — non-blocking version.

Mirror of :mod:`examples.basic` using :class:`railtech_mme.AsyncMME`.

Run with::

    export RAILTECH_API_KEY=mme_live_...
    python examples/async_basic.py
"""

from __future__ import annotations

import asyncio

from railtech_mme import AsyncMME


async def main() -> None:
    async with AsyncMME() as mme:
        # 1. Save a few memories — concurrently, since we can.
        await asyncio.gather(
            mme.save("I prefer dark chocolate over milk chocolate."),
            mme.save("I'm allergic to peanuts."),
            mme.save("My favorite cuisine is Thai."),
        )

        # 2. Retrieve relevant memories for a new prompt.
        #    The prompt's keywords ("food", "allergies") seed tag-graph
        #    propagation against the tags MME assigned at save-time.
        pack = await mme.inject(
            "What are my food preferences and allergies?",
            token_budget=1024,
        )
        print(
            f"Pack {pack.pack_id} — {len(pack.items)} items, "
            f"{pack.total_tokens}/{pack.token_budget} tokens"
        )

        for item in pack.items:
            print(f"  - {item.title}")
            if item.score is not None:
                print(f"    score: {item.score.total:.3f}")
            print(f"    {item.excerpt}")

        # 3. Tell MME the pack was useful — improves retrieval over time
        await mme.feedback(pack_id=pack.pack_id, accepted=True)


if __name__ == "__main__":
    asyncio.run(main())
