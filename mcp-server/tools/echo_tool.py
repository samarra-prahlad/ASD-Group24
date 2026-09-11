from mcp_instance import mcp


def echo(message: str) -> dict:
    """Reference tool: returns the input it was given."""
    return {"echo": message}


mcp.tool()(echo)
