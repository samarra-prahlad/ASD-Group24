import json

import pytest

from coordinator import AWAITING, Coordinator, InvalidDecision, WorkflowNotFound, WorkflowStateError
from store import WorkflowStore
from tests.conftest import FakeLLM


def _events(store):
    with open(store.audit_path) as f:
        return [json.loads(line)["event"] for line in f]


def test_runs_agents_in_order_and_waits_for_human(coordinator, fake_llm, evidence):
    wf = coordinator.run("Summarise invoices", "billing", evidence)
    assert fake_llm.calls == ["planner", "worker", "reviewer"]
    assert wf["status"] == AWAITING
    assert all(wf["steps"][s]["status"] == "completed" for s in ("planner", "worker", "reviewer"))
    assert wf["evidence_count"] == 2
    assert wf["final_output"] is None


def test_audit_log_records_full_coordination(coordinator, store, evidence):
    coordinator.run("Summarise invoices", "billing", evidence)
    assert _events(store) == [
        "workflow_started",
        "agent_started", "agent_completed",
        "agent_started", "agent_completed",
        "agent_started", "agent_completed",
        "awaiting_human_review",
    ]


def test_failure_stops_workflow(store, evidence):
    llm = FakeLLM(fail_role="worker")
    wf = Coordinator(llm, store).run("x", "billing", evidence)
    assert wf["status"] == "failed"
    assert "reviewer" not in wf["steps"]
    assert llm.calls == ["planner", "worker"]
    assert "workflow_failed" in _events(store)


@pytest.mark.parametrize("decision,status", [
    ("approve", "approved"),
    ("partially_accept", "partially_approved"),
    ("reject", "rejected"),
])
def test_human_decisions(coordinator, evidence, decision, status):
    wf = coordinator.run("x", "billing", evidence)
    done = coordinator.review(wf["workflow_id"], decision, "samarra", "checked")
    assert done["status"] == status
    assert done["human_review"]["reviewer"] == "samarra"
    if decision == "reject":
        assert done["final_output"] is None
    else:
        assert done["final_output"] == wf["steps"]["worker"]["output"]


def test_correct_requires_and_uses_correction(coordinator, evidence):
    wf = coordinator.run("x", "billing", evidence)
    with pytest.raises(InvalidDecision):
        coordinator.review(wf["workflow_id"], "correct", "samarra")
    done = coordinator.review(wf["workflow_id"], "correct", "samarra", correction="Owed: 530.00")
    assert done["status"] == "corrected"
    assert done["final_output"] == "Owed: 530.00"


def test_cannot_review_twice(coordinator, evidence):
    wf = coordinator.run("x", "billing", evidence)
    coordinator.review(wf["workflow_id"], "approve", "samarra")
    with pytest.raises(WorkflowStateError):
        coordinator.review(wf["workflow_id"], "reject", "samarra")


def test_invalid_decision_and_unknown_workflow(coordinator, evidence):
    wf = coordinator.run("x", "billing", evidence)
    with pytest.raises(InvalidDecision):
        coordinator.review(wf["workflow_id"], "maybe", "samarra")
    with pytest.raises(WorkflowNotFound):
        coordinator.review("wf-missing", "approve", "samarra")


def test_history_survives_restart(coordinator, store, evidence, tmp_path):
    wf = coordinator.run("x", "billing", evidence)
    coordinator.review(wf["workflow_id"], "approve", "samarra")
    reloaded = WorkflowStore(str(tmp_path))
    assert reloaded.get(wf["workflow_id"])["status"] == "approved"
