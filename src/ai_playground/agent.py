import os
from datetime import date as _date

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import RunContext
from tavily import TavilyClient

from ai_playground.prompts import goal, instructions, knowledge, role


class Agent:
    def __init__(self, model: str = "gemini-3.6-flash"):
        self.name = "Pydantic Agent"
        self.agent = PydanticAgent(
            f"google:{model}",
            system_prompt="\n".join([role, goal, instructions, knowledge]),
        )
        self._tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        self._register_tools()
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

    def chat(self, message: str) -> str:
        try:
            result = self.agent.run_sync(message, message_history=self.messages)
            self.messages.extend(result.new_messages())
            return result.output
        except Exception as e:
            print(f"Error in chat: {e}")
            return "Sorry, I encountered an error processing your request."

    def clear_chat(self) -> bool:
        self.messages = []
        return True
