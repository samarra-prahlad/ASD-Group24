import asyncio
import json
from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession

# A mix of valid IDs (across different doctors/specialties) plus one
# invalid ID to confirm the error path also works correctly.
TEST_IDS = [102, 120, 119, 105, 140, 999999]

EXPECTED_KEYS = {
    "id", "patient_id", "doctor_id", "doctor_name",
    "doctor_specialty", "date", "time", "status",
}


async def check_appointment(session, appointment_id):
    result = await session.call_tool(
        "appointments_get_appointment",
        {"appointment_id": appointment_id},
    )
    data = json.loads(result.content[0].text)

    if "error" in data:
        print(f"[id={appointment_id}] Error response: {data}")
        return

    missing = EXPECTED_KEYS - data.keys()
    extra = data.keys() - EXPECTED_KEYS
    id_matches = data.get("id") == appointment_id

    if not missing and not extra and id_matches:
        print(f"[id={appointment_id}] OK — {data['doctor_name']} ({data['doctor_specialty']}), {data['date']} {data['time']}, status={data['status']}")
    else:
        print(f"[id={appointment_id}] UNEXPECTED SHAPE — missing={missing}, extra={extra}, id_matches={id_matches}")
        print(f"    Raw: {data}")


async def main():
    async with streamablehttp_client("http://localhost:7000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for appointment_id in TEST_IDS:
                await check_appointment(session, appointment_id)

asyncio.run(main())