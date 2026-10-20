import asyncio
import json
import os

import requests
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SHARED_ACCESS_API_URL = os.getenv("SHARED_ACCESS_API_URL", "http://localhost:5000")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://localhost:7001")
MCP_SERVER_MCP_URL = os.getenv("MCP_SERVER_MCP_URL", "http://localhost:7000/mcp")
RAG_SERVER_MCP_URL = os.getenv("RAG_SERVER_MCP_URL", "http://localhost:7001/mcp")
MCP_TEST_INVOICE_ID = os.getenv("MCP_TEST_INVOICE_ID", "INV-1001")
RAG_TEST_QUERY = os.getenv("RAG_TEST_QUERY", "What does partially paid mean?")


def check(label, method, url, **kwargs):
    try:
        response = requests.request(method, url, timeout=5, **kwargs)
        content_ok = bool(response.text and response.text.strip())
        return f"{label} -> HTTP {response.status_code}, content_ok={content_ok}"
    except Exception as exc:
        return f"{label} -> error: {exc}"


def observe_shared_access():
    result = check("shared-access-api", "GET", f"{SHARED_ACCESS_API_URL}/validate?patient_id=101")
    print(f"  Checked {result}")
    return result


def observe_rag_server():
    result = check("rag-server", "GET", f"{RAG_SERVER_URL}/health")
    print(f"  Checked {result}")
    return result


def observe_all_services(plan):
    results = [observe_shared_access(), observe_rag_server()]

    for service in plan["services"]:
        port = service["backend_port"]
        url = f"http://localhost:{port}/"
        result = check(f"{service['name']}-backend", "GET", url)
        print(f"  Checked {result}")
        results.append(result)

    return results


async def _list_mcp_tools(url):
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result.tools


async def _call_mcp_tool(url, tool_name, arguments):
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


def _tool_result_to_json(call_result):
    for item in call_result.content:
        text = getattr(item, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    return {}


def observe_mcp_mode():
    """Real MCP validation: connect to the MCP server, confirm it exposes a
    structured tool schema, then invoke a real tool and check the result
    has the expected shape."""
    results = []

    try:
        tools = asyncio.run(_list_mcp_tools(MCP_SERVER_MCP_URL))
    except Exception as exc:
        result = f"mcp-server -> error connecting/listing tools: {exc}"
        print(f"  Checked {result}")
        return [result]

    tool_names = [t.name for t in tools]
    result = (
        f"mcp-server -> tools_listed={len(tools)} ({', '.join(tool_names) or 'none'}), "
        f"structured_schema_ok={len(tools) > 0}"
    )
    print(f"  Checked {result}")
    results.append(result)

    if "billing_get_invoice_status" in tool_names:
        try:
            call_result = asyncio.run(
                _call_mcp_tool(
                    MCP_SERVER_MCP_URL,
                    "billing_get_invoice_status",
                    {"invoice_id": MCP_TEST_INVOICE_ID},
                )
            )
            payload = _tool_result_to_json(call_result)
            is_error = getattr(call_result, "isError", False)
            result = (
                f"billing_get_invoice_status(invoice_id={MCP_TEST_INVOICE_ID}) -> "
                f"isError={is_error}, structured_result_ok={bool(payload)}, "
                f"keys={list(payload.keys())}"
            )
            if is_error:
                error_text = ""
                for item in call_result.content:
                    error_text = getattr(item, "text", "") or error_text
                result += f", note=tool not yet implemented ({error_text})"
        except Exception as exc:
            result = f"billing_get_invoice_status(invoice_id={MCP_TEST_INVOICE_ID}) -> error: {exc}"
        print(f"  Checked {result}")
        results.append(result)
    else:
        result = "billing_get_invoice_status -> skipped, not registered on MCP server"
        print(f"  Checked {result}")
        results.append(result)

    if "echo" in tool_names:
        try:
            call_result = asyncio.run(
                _call_mcp_tool(MCP_SERVER_MCP_URL, "echo", {"message": "agentic-loop validation"})
            )
            is_error = getattr(call_result, "isError", False)
            text = ""
            for item in call_result.content:
                text = getattr(item, "text", "") or text
            result = f"echo(message='agentic-loop validation') -> isError={is_error}, response={text!r}"
        except Exception as exc:
            result = f"echo -> error: {exc}"
        print(f"  Checked {result}")
        results.append(result)

    return results


def observe_rag_mode():
    """Real RAG validation: call the shared RAG server's answer_question MCP
    tool and check the Grounded Answer Contract fields are present."""
    try:
        call_result = asyncio.run(
            _call_mcp_tool(
                RAG_SERVER_MCP_URL,
                "answer_question",
                {"query": RAG_TEST_QUERY, "top_k": 5},
            )
        )
        payload = _tool_result_to_json(call_result)
        has_citations = bool(payload.get("citations"))
        confidence = payload.get("confidence_category")
        status = payload.get("status")
        result = (
            f"rag-server.answer_question(query={RAG_TEST_QUERY!r}) -> "
            f"status={status}, citations_present={has_citations}, "
            f"confidence_category={confidence}"
        )
    except Exception as exc:
        result = f"rag-server.answer_question -> error: {exc}"

    print(f"  Checked {result}")
    return [result]
