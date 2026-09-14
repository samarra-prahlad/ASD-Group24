from mcp_instance import mcp


def get_order_status(order_id: int) -> dict:
    """Real-time status of a specific lab order."""
    # TODO: implement real logic against your feature's backend/database
    raise NotImplementedError("TODO: implement get_order_status")


mcp.tool(name="labtests_get_order_status")(get_order_status)
