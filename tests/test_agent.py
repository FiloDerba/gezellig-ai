from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from ai_playground.agent import Agent as PlaygroundAgent
from ai_playground.prompts import goal, instructions, knowledge, role


def test_date_tool_returns_a_date_string():
    result = PlaygroundAgent.date_tool()
    assert len(result) > 0


def test_agent_runs_with_test_model():
    system_prompt = "\n".join([role, goal, instructions, knowledge])
    agent = Agent(TestModel(), system_prompt=system_prompt)
    result = agent.run_sync("hello")
    assert result.output
