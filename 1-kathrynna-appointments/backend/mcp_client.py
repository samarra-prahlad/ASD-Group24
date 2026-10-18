import asyncio
import json
import os

from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# host.docker.internal already resolves for this container (extra_hosts in compose)
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:7000/mcp")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://host.docker.internal:7001/mcp")


async def call_get_appointment(appointment_id: int) -> dict:
    """Calls the shared MCP server's appointments_get_appointment tool
    and returns the parsed JSON result."""
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "appointments_get_appointment",
                {"appointment_id": appointment_id},
            )
            return json.loads(result.content[0].text)


async def _call_rag_async(query, top_k):
    async with streamablehttp_client(RAG_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(
                "answer_question", {"query": query, "top_k": top_k}
            )


def call_rag_answer_question(query, top_k=5):
    """Returns the RAG server's parsed answer dict, or None if the server
    is unreachable or the response can't be parsed (callers then fall back
    to the plain LLM)."""
    try:
        result = asyncio.run(_call_rag_async(query, top_k))
    except Exception:
        return None

    if getattr(result, "isError", False):
        return None

    try:
        return json.loads(result.content[0].text)
    except (IndexError, AttributeError, TypeError, json.JSONDecodeError):
        return None