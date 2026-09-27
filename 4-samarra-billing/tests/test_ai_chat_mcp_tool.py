"""
Pytest suite for MCP tool and RAG grounding in the billing AI chat
endpoints (backend/app.py: extract_invoice_id, call_invoice_status_tool,
call_rag_answer_question, build_grounded_prompt, and the /ai/chat routes
using them).

Run with:
    pytest tests/test_ai_chat_mcp_tool.py -v
"""

import os
import importlib.util
from unittest.mock import patch

import pytest

FEATURE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(FEATURE_ROOT, "backend")


def _load_module(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


billing_backend_app = _load_module("billing_backend_app_mcp", os.path.join(BACKEND_DIR, "app.py"))


@pytest.fixture
def client():
    billing_backend_app.app.config["TESTING"] = True
    with billing_backend_app.app.test_client() as test_client:
        yield test_client


class TestExtractInvoiceId:

    def test_extracts_id_from_plain_mention(self):
        assert billing_backend_app.extract_invoice_id("what's the status of invoice 5") == 5

    def test_extracts_id_with_hash(self):
        assert billing_backend_app.extract_invoice_id("check invoice #12 please") == 12

    def test_returns_none_when_no_invoice_mentioned(self):
        assert billing_backend_app.extract_invoice_id("how does insurance coverage work") is None

    def test_returns_none_for_empty_message(self):
        assert billing_backend_app.extract_invoice_id("") is None

    def test_is_case_insensitive(self):
        assert billing_backend_app.extract_invoice_id("Invoice 7 status?") == 7


class TestBuildGroundedPrompt:

    def test_returns_message_unchanged_when_no_invoice_data(self):
        result = billing_backend_app.build_grounded_prompt("hello", None)
        assert result == "hello"

    def test_appends_invoice_data_when_present(self):
        invoice_data = {"invoice_id": 5, "status": "pending"}
        result = billing_backend_app.build_grounded_prompt("what's the status", invoice_data)

        assert "what's the status" in result
        assert '"status": "pending"' in result


class TestAiChatWithToolGrounding:

    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_calls_tool_when_invoice_mentioned(self, mock_ollama, mock_tool, client):
        mock_tool.return_value = {"invoice_id": 5, "status": "pending", "patient_owed_amount": 165.0}
        mock_ollama.return_value = ("Invoice 5 is pending, with $165.00 owed.", None)

        response = client.post("/ai/chat", json={"message": "what's the status of invoice 5"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["reply"] == "Invoice 5 is pending, with $165.00 owed."
        assert data["tool_used"] == "billing_get_invoice_status"
        assert data["tool_result"]["status"] == "pending"
        mock_tool.assert_called_once_with(5)

    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_skips_tool_when_no_invoice_mentioned(self, mock_ollama, mock_tool, mock_rag, client):
        mock_rag.return_value = None  # simulate RAG unreachable, so this falls through to Ollama
        mock_ollama.return_value = ("Insurance coverage varies by plan.", None)

        response = client.post("/ai/chat", json={"message": "how does insurance coverage work"})

        assert response.status_code == 200
        data = response.get_json()
        assert "tool_used" not in data
        mock_tool.assert_not_called()

    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_still_answers_when_tool_returns_none(self, mock_ollama, mock_tool, client):
        mock_tool.return_value = None
        mock_ollama.return_value = ("I couldn't find that invoice.", None)

        response = client.post("/ai/chat", json={"message": "what's the status of invoice 999"})

        assert response.status_code == 200
        data = response.get_json()
        assert "tool_used" not in data
        assert data["reply"] == "I couldn't find that invoice."

    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_missing_message_returns_400(self, mock_ollama, client):
        response = client.post("/ai/chat", json={})

        assert response.status_code == 400
        mock_ollama.assert_not_called()

class TestAiChatWithRagGrounding:

    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_uses_rag_when_no_invoice_mentioned(self, mock_ollama, mock_tool, mock_rag, client):
        mock_rag.return_value = {
            "status": "ok",
            "answer": "A pending invoice means payment has not been received yet.",
            "citations": [{"source_id": "billing/invoice_statuses.md", "chunk_id": "abc123"}],
            "confidence_category": "Low",
        }
        mock_ollama.return_value = ("This should not be called directly", None)

        response = client.post("/ai/chat", json={"message": "what does pending invoice status mean"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["reply"] == "A pending invoice means payment has not been received yet."
        assert data["confidence_category"] == "Low"
        assert data["citations"] == [{"source_id": "billing/invoice_statuses.md", "chunk_id": "abc123"}]
        mock_rag.assert_called_once_with("what does pending invoice status mean")
        mock_tool.assert_not_called()
        mock_ollama.assert_not_called()

    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_shows_insufficient_context(self, mock_ollama, mock_tool, mock_rag, client):
        mock_rag.return_value = {
            "status": "insufficient_context",
            "answer": "There is not enough information in the knowledge base to answer this question.",
            "citations": [],
            "confidence_category": "Insufficient",
        }

        response = client.post("/ai/chat", json={"message": "what is the capital of France"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["confidence_category"] == "Insufficient"
        assert data["reply"] == "There is not enough information in the knowledge base to answer this question."
        mock_ollama.assert_not_called()

    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_falls_back_to_ollama_when_rag_unreachable(self, mock_ollama, mock_tool, mock_rag, client):
        mock_rag.return_value = None
        mock_ollama.return_value = ("A generic, ungrounded answer.", None)

        response = client.post("/ai/chat", json={"message": "what does pending invoice status mean"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["reply"] == "A generic, ungrounded answer."
        assert "confidence_category" not in data
        mock_ollama.assert_called_once()

    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_still_uses_mcp_tool_when_invoice_mentioned(self, mock_ollama, mock_rag, mock_tool, client):
        mock_tool.return_value = {"invoice_id": 5, "status": "pending", "patient_owed_amount": 165.0}
        mock_ollama.return_value = ("Invoice 5 is pending, with $165.00 owed.", None)

        response = client.post("/ai/chat", json={"message": "what's the status of invoice 5"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["tool_used"] == "billing_get_invoice_status"
        mock_rag.assert_not_called()
class TestAiChatHtmlWithRagGrounding:

    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_html_uses_rag_when_no_invoice_mentioned(self, mock_ollama, mock_tool, mock_rag, client):
        mock_rag.return_value = {
            "status": "ok",
            "answer": "A pending invoice means payment has not been received yet.",
            "citations": [{"source_id": "billing/invoice_statuses.md", "chunk_id": "abc123"}],
            "confidence_category": "Low",
        }
        mock_ollama.return_value = ("This should not be called directly", None)

        response = client.post("/ai/chat/html", data={"message": "what does pending invoice status mean"})

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "A pending invoice means payment has not been received yet." in html
        assert "confidence-badge" in html
        assert "confidence-low" in html
        assert "Low" in html
        assert "billing/invoice_statuses.md" in html
        assert "citation-list" in html
        mock_rag.assert_called_once_with("what does pending invoice status mean")
        mock_tool.assert_not_called()
        mock_ollama.assert_not_called()

    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_html_shows_insufficient_context(self, mock_ollama, mock_tool, mock_rag, client):
        mock_rag.return_value = {
            "status": "insufficient_context",
            "answer": "There is not enough information in the knowledge base to answer this question.",
            "citations": [],
            "confidence_category": "Insufficient",
        }

        response = client.post("/ai/chat/html", data={"message": "what is the capital of France"})

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "chat-insufficient" in html
        assert "confidence-insufficient" in html
        assert "don't have enough information" in html
        mock_ollama.assert_not_called()

    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_html_falls_back_to_ollama_when_rag_unreachable(self, mock_ollama, mock_tool, mock_rag, client):
        mock_rag.return_value = None
        mock_ollama.return_value = ("A generic, ungrounded answer.", None)

        response = client.post("/ai/chat/html", data={"message": "what does pending invoice status mean"})

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "A generic, ungrounded answer." in html
        assert "confidence-badge" not in html
        assert "citation-list" not in html
        mock_ollama.assert_called_once()

    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_html_still_uses_mcp_tool_when_invoice_mentioned(self, mock_ollama, mock_rag, mock_tool, client):
        mock_tool.return_value = {"invoice_id": 5, "status": "pending", "patient_owed_amount": 165.0}
        mock_ollama.return_value = ("Invoice 5 is pending, with $165.00 owed.", None)

        response = client.post("/ai/chat/html", data={"message": "what's the status of invoice 5"})

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert "Invoice 5 is pending, with $165.00 owed." in html
        mock_rag.assert_not_called()

    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_html_missing_message_returns_400(self, mock_ollama, client):
        response = client.post("/ai/chat/html", data={"message": "   "})

        assert response.status_code == 400
        mock_ollama.assert_not_called()

    @patch.object(billing_backend_app, "call_rag_answer_question")
    @patch.object(billing_backend_app, "call_invoice_status_tool")
    @patch.object(billing_backend_app, "call_ollama")
    def test_ai_chat_html_escapes_user_message(self, mock_ollama, mock_tool, mock_rag, client):
        mock_rag.return_value = None
        mock_ollama.return_value = ("reply", None)

        response = client.post("/ai/chat/html", data={"message": "<script>alert(1)</script>"})

        html = response.get_data(as_text=True)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html