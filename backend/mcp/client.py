"""Thin client for talking to the GitHub MCP server over stdio.

The github-mcp-server binary (https://github.com/github/github-mcp-server) is
expected to be available on PATH (configurable via GITHUB_MCP_COMMAND) and is
launched as a subprocess per call, authenticated via GITHUB_TOKEN.
"""

import asyncio
import concurrent.futures
import json
import logging
import os
import shlex

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ..config import settings

logger = logging.getLogger(__name__)


async def _call_tool_async(tool_name: str, arguments: dict):
    env = {**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": settings.github_token}

    # GITHUB_MCP_COMMAND is a full command line, e.g.:
    #   github-mcp-server stdio
    #   C:\tools\github-mcp-server.exe stdio
    #   docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server
    parts = shlex.split(settings.github_mcp_command, posix=False)
    if not parts:
        raise RuntimeError("GITHUB_MCP_COMMAND is not configured.")

    server_params = StdioServerParameters(
        command=parts[0],
        args=parts[1:],
        env=env,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)

            texts = [c.text for c in result.content if hasattr(c, "text")]
            payload = "\n".join(texts)

            if result.isError:
                raise RuntimeError(f"GitHub MCP tool '{tool_name}' returned an error: {payload}")

            try:
                return json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                return payload


def call_github_tool(tool_name: str, arguments: dict):
    """Synchronous wrapper around an MCP tool call.

    Runs the async MCP session in its own thread + event loop so it can be
    called safely from within FastAPI's already-running event loop.
    """
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN is not configured.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(_call_tool_async(tool_name, arguments)))
        return future.result(timeout=30)
