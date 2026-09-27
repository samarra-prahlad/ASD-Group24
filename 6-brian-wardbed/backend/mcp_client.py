import asyncio
import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_SERVER_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://host.docker.internal:7000/mcp"
)


async def _call_get_current_bed(patient_id: int) -> dict:
    async with streamable_http_client(MCP_SERVER_URL) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool("wardbed_get_current_bed", {"patient_id": patient_id})

            if result.isError:
                raise RuntimeError("MCP tool returned an error")

            if not result.content:
                raise RuntimeError("MCP tool returned no content")

            content = result.content[0]

            if hasattr(content, "text"):
                return json.loads(content.text)

            raise RuntimeError("Unexpected MCP response format")


def call_get_current_bed(patient_id: int) -> dict:
    return asyncio.run(_call_get_current_bed(patient_id))