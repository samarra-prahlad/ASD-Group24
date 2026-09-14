from mcp_instance import mcp


def get_change_request_status(request_id: int) -> dict:
    """Check whether a record change request has been processed."""
    # TODO: implement real logic against your feature's backend/database
    raise NotImplementedError("TODO: implement get_change_request_status")


mcp.tool(name="ehr_get_change_request_status")(get_change_request_status)
