import asyncio
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

async def main():
    async with streamablehttp_client("http://localhost:7000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "appointments_get_appointment",
                {"appointment_id": 102}  # replace 1 with a real ID from curl output
            )
            print("Tool result:", result)

asyncio.run(main())