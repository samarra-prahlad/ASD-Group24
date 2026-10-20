import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:7000/mcp")


def _extract_result(result):
    if result.isError:
        raise RuntimeError(f"MCP tool returned an error: {result.content}")
    for block in result.content:
        if hasattr(block, "text"):
            try:
                return json.loads(block.text)
            except (json.JSONDecodeError, TypeError):
                return block.text
    return None


async def _call_tool(tool_name: str, arguments: dict):
    async with streamablehttp_client(MCP_SERVER_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return _extract_result(result)


def call_get_change_request_status(request_id: int) -> dict:
    """Synchronous wrapper so a Flask route can call this directly."""
    return asyncio.run(_call_tool("ehr_get_change_request_status", {"request_id": request_id}))


if __name__ == "__main__":
    print(call_get_change_request_status(1))