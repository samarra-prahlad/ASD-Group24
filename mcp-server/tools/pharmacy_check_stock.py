from mcp_instance import mcp


def check_stock(medication_name: str) -> dict:
    """Check current stock."""
    # TODO: implement real logic against your feature's backend/database
    raise NotImplementedError("TODO: implement check_stock")


mcp.tool(name="pharmacy_check_stock")(check_stock)
