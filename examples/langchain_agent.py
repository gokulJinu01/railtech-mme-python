"""LangChain example: an agent that saves and retrieves from MME.

Install the extras first::

    pip install "railtech-mme[langchain]" langchain langchain-anthropic

Then run::

    export RAILTECH_API_KEY=mme_live_...
    export ANTHROPIC_API_KEY=sk-ant-...
    python examples/langchain_agent.py
"""

from __future__ import annotations

from railtech_mme import MME
from railtech_mme.langchain import MMEInjectTool, MMESaveTool


def main() -> None:
    # Needs: pip install langchain langchain-anthropic
    from langchain.agents import AgentExecutor, create_react_agent  # type: ignore[import-not-found]
    from langchain_anthropic import ChatAnthropic  # type: ignore[import-not-found]
    from langchain_core.prompts import PromptTemplate  # type: ignore[import-not-found]

    mme = MME()
    tools = [MMESaveTool(mme=mme), MMEInjectTool(mme=mme)]

    llm = ChatAnthropic(model="claude-haiku-4-5")

    prompt = PromptTemplate.from_template(
        "You are a helpful assistant with persistent memory via MME.\n"
        "Available tools: {tools}\n"
        "Tool names: {tool_names}\n\n"
        "Question: {input}\n"
        "{agent_scratchpad}"
    )

    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    executor.invoke({"input": "Remember that my favorite colour is violet."})
    executor.invoke({"input": "What's my favorite colour?"})


if __name__ == "__main__":
    main()
