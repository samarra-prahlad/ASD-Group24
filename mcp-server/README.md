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

## Getting Started (Team Instructions)

1. Pull latest main:
   ```
   git checkout main
   git pull
   ```

2. Read this file first — it covers how to run the server, test it, and add your own tool.

3. Run it locally to confirm it works on your machine:
   ```
   cd mcp-server
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt --break-system-packages
   python server.py
   ```
   You should see `Server status: RUNNING` and Uvicorn listening on port 7000.

4. Your MCP tool: check `MCP_Tools_RAG_Areas.md` for your feature's proposed tool(s) — it's a draft, adjust it if it doesn't fit your data model. To build yours:
   - Copy `tools/echo_tool.py` to a new file (e.g. `tools/get_invoice_status.py`)
   - Write your tool's logic as a plain function
   - Register it: `mcp.tool()(your_function)`
   - No other file needs to change — it's auto-discovered

5. Your backend/API needs to call this server via `http://host.docker.internal:7000/mcp` (not `localhost`, since your backend runs in a container). `client_test.py` shows a working example of connecting and calling a tool — use it as your reference for wiring your own backend as an MCP client.

6. **Internal deadline:** by Sunday, have your backend able to round-trip one real MCP call to your own tool (frontend doesn't need to show it yet — that's next week).

RAG server isn't built yet — contract is designed (`MCP_RAG_Contracts.md`) but no code. If you know what content should ground your feature's RAG answers (policies, FAQs, reference docs), start collecting it now — you'll drop it into `rag-server/knowledge/<your_feature>/` once it exists.

Ping Samarra if `host.docker.internal` doesn't resolve from your container or anything here doesn't match what you're seeing.