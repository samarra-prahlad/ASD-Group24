from mcp_instance import mcp
import tools  # noqa: F401  (import triggers tool registration)

AVAILABLE_TOOLS = ["echo"]

if __name__ == "__main__":
    print("Starting Group24 Shared MCP Server...")
    print("Server status: RUNNING")
    print("Available tools:")
    for tool in AVAILABLE_TOOLS:
        print(f"- {tool}")
    mcp.run(transport="streamable-http")
