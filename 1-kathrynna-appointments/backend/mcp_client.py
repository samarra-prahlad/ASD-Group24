import os
import json
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# Inside a Docker container, "localhost" refers to the container itself, not
# the host machine where the shared MCP server runs — so this must use
# host.docker.internal, per the MCP server's README.
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://host.docker.internal:7000/mcp")


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
            text = result.content[0].text
            return json.loads(text)