# Shared MCP Server — Group 24

Non-containerised MCP server using the real MCP Python SDK (`mcp<2`, FastMCP), running on port 7000.

## Run it

```
pip install -r requirements.txt --break-system-packages
python server.py
```

You should see:
```
Starting Group24 Shared MCP Server...
Server status: RUNNING
Available tools:
- echo
```
followed by Uvicorn startup logs confirming it's listening on `http://0.0.0.0:7000`.

## Run tests

```
pytest tests/ -v
```

## Reaching this server from your feature's backend

- **From your local machine:** `http://localhost:7000/mcp`
- **From inside a Docker container** (your backend/API service): `http://host.docker.internal:7000/mcp`

Use the MCP Python SDK's `streamablehttp_client` + `ClientSession` to connect — see `client_test.py` in this folder for a working example of listing tools and calling one.

## Add your own tool

1. Copy `tools/echo_tool.py` to a new file, e.g. `tools/get_invoice_status.py`
2. Write a plain Python function with your tool's logic
3. Register it against the shared `mcp` instance: `mcp.tool()(your_function)`
4. That's it — no other file needs to change. Tools are auto-discovered via `tools/__init__.py` on server startup.

See `MCP_Tools_RAG_Areas.md` (shared team doc) for your feature's proposed tool(s) and suggested input/output shape.

## Status

- MCP server: built, tested, running — reference `echo` tool in place
- Real per-feature tools: not yet built (Week 2)
- Boundary documentation (`boundary-analysis.md`): not yet written
- RAG server: not yet built (contract designed, see `MCP_RAG_Contracts.md`)