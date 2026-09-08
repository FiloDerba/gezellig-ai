import pytest
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from ai_playground.agent import Agent as PlaygroundAgent
from ai_playground.prompts import goal, instructions, knowledge, role


def quiet_model(**kwargs) -> TestModel:
    """TestModel calls every registered tool by default, and web_search_tool is a real
    Tavily request. Tests that only care about the conversation must opt out of that."""
    return TestModel(call_tools=[], **kwargs)


@pytest.fixture
def agent() -> PlaygroundAgent:
    """The real wrapper, wired to TestModel so no API key or network is needed."""
    return PlaygroundAgent(quiet_model())


def test_date_tool_returns_a_date_string():
    assert len(PlaygroundAgent.date_tool()) > 0


def test_agent_runs_with_test_model():
    system_prompt = "\n".join([role, goal, instructions, knowledge])
    result = Agent(TestModel(), system_prompt=system_prompt).run_sync("hello")
    assert result.output


class ModelSelectionTests:
    def test_bare_name_is_treated_as_gemini(self):
        assert PlaygroundAgent("gemini-3.6-flash").agent.model.system == "google"

    def test_a_model_instance_is_passed_through(self, agent):
        assert isinstance(agent.agent.model, TestModel)


class ExtraContextTests:
    def test_extra_context_is_appended_to_the_system_prompt(self):
        built = PlaygroundAgent(quiet_model(), extra_context="The learner knows: fiets, gracht.")
        prompts = built.agent._instructions or ""
        for source in built.agent._system_prompts:
            prompts += source
        assert "fiets, gracht" in prompts

    def test_empty_parts_are_not_joined_in(self):
        built = PlaygroundAgent(quiet_model())
        assert "\n\n\n" not in "".join(built.agent._system_prompts)


class WebSearchTests:
    def test_web_search_returns_the_result_list(self, agent, monkeypatch):
        monkeypatch.setattr(
            agent._tavily_client, "search", lambda query: {"results": [{"title": query}]}
        )
        assert "windmills" in agent.web_search("windmills")

    def test_missing_results_key_does_not_raise(self, agent, monkeypatch):
        monkeypatch.setattr(agent._tavily_client, "search", lambda query: {})
        assert agent.web_search("anything") == "[]"

    def test_both_tools_are_registered(self, agent):
        assert {"date", "web_search_tool"} <= set(agent.agent._function_toolset.tools)


class StatelessRunTests:
    def test_run_returns_reply_and_new_messages(self, agent):
        reply, new_messages = agent.run("hallo")
        assert reply
        assert new_messages

    def test_run_leaves_the_instance_history_alone(self, agent):
        agent.run("hallo")
        assert agent.messages == []

    def test_run_accepts_a_prior_history(self, agent):
        _, first = agent.run("hallo")
        reply, second = agent.run("en nu?", first)
        assert reply
        # Only the new turn comes back, so callers can append without duplicating.
        assert second != first

    def test_run_propagates_errors(self):
        class Boom(TestModel):
            async def request(self, *args, **kwargs):
                raise RuntimeError("model exploded")

        with pytest.raises(RuntimeError, match="model exploded"):
            PlaygroundAgent(Boom()).run("hallo")


class StatefulChatTests:
    def test_chat_accumulates_history(self, agent):
        agent.chat("hallo")
        first = len(agent.messages)
        agent.chat("en nu?")
        assert len(agent.messages) > first

    def test_chat_swallows_errors_for_the_cli(self):
        class Boom(TestModel):
            async def request(self, *args, **kwargs):
                raise RuntimeError("model exploded")

        assert "Sorry" in PlaygroundAgent(Boom()).chat("hallo")

    def test_clear_chat_empties_history(self, agent):
        agent.chat("hallo")
        assert agent.clear_chat() is True
        assert agent.messages == []
