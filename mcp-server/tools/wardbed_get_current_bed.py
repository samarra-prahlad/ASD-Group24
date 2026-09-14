from mcp_instance import mcp


def get_current_bed(patient_id: int) -> dict:
    """Bed currently assigned to a patient."""
    # TODO: implement real logic against your feature's backend/database
    raise NotImplementedError("TODO: implement get_current_bed")


mcp.tool(name="wardbed_get_current_bed")(get_current_bed)
