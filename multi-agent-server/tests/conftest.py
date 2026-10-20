import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from coordinator import Coordinator  # noqa: E402
from store import WorkflowStore  # noqa: E402

EVIDENCE = [
    {"invoice_id": 101, "patient_id": 1, "amount_owed": 50.0, "status": "pending"},
    {"invoice_id": 102, "patient_id": 1, "amount_owed": 480.0, "status": "overdue"},
]


class FakeLLM:
    """Stands in for Ollama. Picks a canned reply based on which agent's system prompt it receives."""

    def __init__(self, fail_role=None, worker_text=None, reviewer_text=None):
        self.calls = []
        self.fail_role = fail_role
        self.replies = {
            "planner": "Objective: summarise invoices.\nSteps: 1. List unpaid.\nApproval: human approves.",
            "worker": worker_text or "Output: 2 unpaid invoices, 530.00 owed.\nEvidence Used: 101, 102",
            "reviewer": reviewer_text or "Risk: LOW\nIssues: None\nCorrections: None\nRecommendation: APPROVE",
        }

    def __call__(self, model, system_prompt, user_prompt):
        role = next(r for r in ("planner", "worker", "reviewer") if f"the {r.capitalize()} agent" in system_prompt)
        self.calls.append(role)
        if role == self.fail_role:
            return None, "LLM unreachable: test"
        return self.replies[role], None


@pytest.fixture
def evidence():
    return [dict(r) for r in EVIDENCE]


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def store(tmp_path):
    return WorkflowStore(str(tmp_path))


@pytest.fixture
def coordinator(fake_llm, store):
    return Coordinator(fake_llm, store)
