import os
from collections.abc import Callable, Sequence
from datetime import date as _date

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import RunContext
from pydantic_ai.models import Model
from tavily import TavilyClient

from ai_playground.prompts import goal, instructions, knowledge, role


class Agent:
    def __init__(
        self,
        model: str | Model = "gemini-3.6-flash",
        extra_context: str = "",
        extra_tools: Sequence[Callable] = (),
    ):
        """`extra_context` is appended to the system prompt, for app-specific knowledge.

        `extra_tools` are plain functions registered alongside the built-in ones, which is
        how a host application gives the agent access to its own data.
        """
        self.name = "Pydantic Agent"
        if isinstance(model, str) and ":" not in model:
            # Bare names mean Gemini; a qualified name or a Model instance is passed through.
            model = f"google:{model}"
        self.agent = PydanticAgent(
            model,
            system_prompt="\n".join(
                part for part in [role, goal, instructions, knowledge, extra_context] if part
            ),
        )
        self._tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        self._register_tools()
        for tool in extra_tools:
            self.agent.tool_plain(tool)
        self.messages = []

    @staticmethod
    def date_tool() -> str:
        return _date.today().strftime("%B %d, %Y")

    def web_search(self, query: str) -> str:
        results = self._tavily_client.search(query)
        return str(results.get("results", []))

    def _register_tools(self):
        @self.agent.tool
        async def date(ctx: RunContext) -> str:
            """Get the current date"""
            return self.date_tool()

        @self.agent.tool
        async def web_search_tool(ctx: RunContext, query: str) -> str:
            """Search the web for information"""
            return self.web_search(query)

    def run(self, message: str, history: list | None = None) -> tuple[str, list]:
        """One turn, holding no state of its own.

        Returns the reply and the messages it produced, so a caller with several
        conversations at once (a web UI, say) can keep each history separately.
        Errors propagate, unlike `chat`.
        """
        result = self.agent.run_sync(message, message_history=history or [])
        return result.output, result.new_messages()

    def chat(self, message: str) -> str:
        try:
            output, new_messages = self.run(message, self.messages)
            self.messages.extend(new_messages)
            return output
        except Exception as e:
            print(f"Error in chat: {e}")
            return "Sorry, I encountered an error processing your request."

    def clear_chat(self) -> bool:
        self.messages = []
        return True
