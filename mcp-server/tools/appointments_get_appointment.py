from mcp_instance import mcp


def get_appointment(appointment_id: int) -> dict:
    """Status/details of a single appointment."""
    # TODO: implement real logic against your feature's backend/database
    raise NotImplementedError("TODO: implement get_appointment")


mcp.tool(name="appointments_get_appointment")(get_appointment)
