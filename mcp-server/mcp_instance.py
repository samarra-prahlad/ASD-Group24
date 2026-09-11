from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Group24 Shared MCP",
    host="0.0.0.0",
    port=7000,
    stateless_http=True,
    json_response=True,
)
