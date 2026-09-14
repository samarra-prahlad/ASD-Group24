from mcp_instance import mcp


def get_invoice_status(invoice_id: int) -> dict:
    """Check an invoice's payment state."""
    # TODO: implement real logic against your feature's backend/database
    raise NotImplementedError("TODO: implement get_invoice_status")


mcp.tool(name="billing_get_invoice_status")(get_invoice_status)
