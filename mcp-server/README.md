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
- ehr_get_change_request_status
- billing_get_invoice_status
- wardbed_get_current_bed
- appointments_get_appointment
- pharmacy_check_stock
- labtests_get_order_status
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

## Implement your tool

Your feature already has a stub file in `tools/` — you don't need to create anything new:

- Div (EHR): `tools/ehr_get_change_request_status.py`
- Samarra (Billing): `tools/billing_get_invoice_status.py`
- Brian (Ward & Bed): `tools/wardbed_get_current_bed.py`
- Kathrynna (Appointments): `tools/appointments_get_appointment.py`
- Will (Pharmacy): `tools/pharmacy_check_stock.py`
- Max (Lab Tests): `tools/labtests_get_order_status.py`

Open your file, replace the `raise NotImplementedError(...)` line with real logic that calls your own backend/database, and you're done — no other file needs to change, and the tool is already registered under a collision-safe name (e.g. `ehr_get_change_request_status`, not just `get_change_request_status`).

**Scope note:** this is intentionally one tool per feature, matching the lab's own reference app (4 tools total for the whole thing, not per feature) and the rubric's actual requirement (every feature demonstrates one working MCP call, not a large tool list). If you want to build more tools later as a stretch goal, follow the same pattern (copy `echo_tool.py`, register with a `<feature>_` prefixed name) — but the one assigned tool is what's required for full marks.

## Add a brand new tool (only if going beyond the required one)

1. Copy `tools/echo_tool.py` to a new file
2. Write a plain Python function with your tool's logic
3. Register it against the shared `mcp` instance with a feature-prefixed name: `mcp.tool(name="yourfeature_toolname")(your_function)`
4. No other file needs to change — tools are auto-discovered via `tools/__init__.py` on server startup, but you do need to add an import line there for your new file

## Status

- MCP server: built, tested, running
- 6 required tool stubs in place (one per feature) — each still raises `NotImplementedError` until the owning teammate implements it
- Boundary documentation (`boundary-analysis.md`): not yet written
- RAG server: skeleton built (folder structure matches Lab 8, `embed_texts` implemented and tested). Corpus building, retrieval, and grounded answering not yet implemented — in progress.

## Getting Started (Team Instructions)

1. Pull latest main:
   ```
   git checkout main
   git pull
   ```

2. Read this file first — it covers how to run the server, test it, and implement your tool.

3. Run it locally to confirm it works on your machine:
   ```
   cd mcp-server
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt --break-system-packages
   python server.py
   ```
   You should see `Server status: RUNNING`, all 7 tools listed, and Uvicorn listening on port 7000.

4. Open your feature's stub file (see the list under "Implement your tool" above) and replace the `NotImplementedError` with real logic.

5. Your backend/API needs to call this server via `http://host.docker.internal:7000/mcp` (not `localhost`, since your backend runs in a container). `client_test.py` shows a working example of connecting and calling a tool — use it as your reference for wiring your own backend as an MCP client.

6. **Internal deadline:** by Sunday, have your backend able to round-trip one real MCP call to your own tool (frontend doesn't need to show it yet — that's next week).

RAG server isn't finished yet — the skeleton and folder structure exist, but retrieval/answering isn't built. Your RAG knowledge folder already exists at `rag-server/knowledge/<your_feature>/` — you can start dropping in `.md` files with policy/procedure content whenever you have downtime; this doesn't depend on the RAG server being finished.

Ping Samarra if `host.docker.internal` doesn't resolve from your container or anything here doesn't match what you're seeing.