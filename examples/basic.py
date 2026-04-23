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
        mme.save("I prefer dark chocolate over milk chocolate.")
        mme.save("I'm allergic to peanuts.")
        mme.save("My favorite cuisine is Thai.")

        # 2. Retrieve relevant memories for a new prompt.
        #    Note: tag-graph retrieval matches keywords in the prompt against
        #    the tags MME assigned at save-time. Prompts that share concrete
        #    words with your saved facts ("food", "allergies") retrieve
        #    reliably even on a brand-new account.
        pack = mme.inject(
            "What are my food preferences and allergies?",
            token_budget=1024,
        )
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
