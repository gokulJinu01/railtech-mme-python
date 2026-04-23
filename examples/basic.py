"""Minimal end-to-end example: save, inject, feedback.

Run with::

    export RAILTECH_API_KEY=mme_live_...
    python examples/basic.py
"""

from __future__ import annotations

from railtech_mme import MME


def main() -> None:
    with MME() as mme:
        # 1. Save a few memories
        mme.save("I prefer dark chocolate over milk.")
        mme.save("My cat's name is Luna.")
        mme.save("I'm allergic to peanuts.")

        # 2. Retrieve relevant memories for a new prompt
        pack = mme.inject("What do I like to eat?", token_budget=1024)
        print(f"Pack {pack.pack_id} — {len(pack.items)} items, "
              f"{pack.total_tokens}/{pack.token_budget} tokens")

        for item in pack.items:
            print(f"  - {item.title}")
            if item.score is not None:
                print(f"    score: {item.score.total:.3f}")
            print(f"    {item.excerpt}")

        # 3. Tell MME the pack was useful — improves retrieval over time
        mme.feedback(pack_id=pack.pack_id, accepted=True)


if __name__ == "__main__":
    main()
