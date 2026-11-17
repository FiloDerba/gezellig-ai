"""The campaign search tools as an MCP server, so any MCP client can use them.

It runs over stdio: the client starts it as a subprocess and talks JSON-RPC on stdin/stdout.
To use it from Claude Code:

    claude mcp add campaign -- uv run --project /path/to/gezellig-ai rag-mcp --hybrid
"""

import argparse
import functools
import sys
from collections.abc import Callable
from contextlib import redirect_stdout

from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from rag_playground import rag
from rag_playground.index import Index, load_index

INSTRUCTIONS = """
Search the user's Dungeons & Dragons campaign, a long first-person story with world-building
sections. search_campaign finds passages by meaning; grep_campaign finds exact names and
phrases. Every result starts with the chapter or section it comes from.
"""


def quiet(tool: Callable[..., str]) -> Callable[..., str]:
    """`tool` with its log lines sent to stderr: on stdio, stdout is the protocol channel."""

    @functools.wraps(tool)
    def wrapper(**arguments: str) -> str:  # wraps() keeps the tool's own signature for MCP
        with redirect_stdout(sys.stderr):
            return tool(**arguments)

    return wrapper


def server(index: Index) -> MCPServer:
    mcp = MCPServer("campaign", instructions=INSTRUCTIONS)
    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)
    for tool in (rag.search_tool(index), rag.grep_tool(index.chunks)):
        mcp.add_tool(quiet(tool), annotations=read_only)
    return mcp


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Serve the campaign search tools over MCP.")
    parser.add_argument("--hybrid", action="store_true", help="search by keyword as well")
    args = parser.parse_args()
    with redirect_stdout(sys.stderr):  # a first run prints embedding progress
        index = load_index(hybrid=args.hybrid)
    server(index).run()  # stdio
