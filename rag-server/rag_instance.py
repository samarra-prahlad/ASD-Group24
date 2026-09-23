from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "Group24 Shared RAG",
    host="0.0.0.0",
    port=7001,
    stateless_http=True,
    json_response=True,
)