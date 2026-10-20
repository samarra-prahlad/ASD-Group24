from agents.planner_agent import plan_workflow
from agents.reviewer_agent import review_output
from agents.worker_agent import generate_output
from tests.conftest import FakeLLM


def test_planner_completes_and_lists_evidence_fields(evidence):
    llm = FakeLLM()
    result = plan_workflow("Summarise invoices", "billing", evidence, llm)
    assert result["status"] == "completed"
    assert "Objective" in result["output"]
    assert llm.calls == ["planner"]


def test_planner_reports_failure_when_llm_unreachable(evidence):
    result = plan_workflow("x", "billing", evidence, FakeLLM(fail_role="planner"))
    assert result["status"] == "failed"
    assert result["output"] is None
    assert "unreachable" in result["error"]


def test_worker_counts_evidence(evidence):
    result = generate_output({"output": "plan"}, "Summarise", evidence, FakeLLM())
    assert result["status"] == "completed"
    assert result["evidence_count"] == 2


def test_reviewer_parses_risk_and_recommendation(evidence):
    worker = {"output": "Evidence Used: 101, 102"}
    result = review_output({"output": "plan"}, worker, evidence, FakeLLM())
    assert result["risk_level"] == "LOW"
    assert result["recommendation"] == "APPROVE"
    assert result["grounding"]["evidence_ids_cited"] >= 2


def test_reviewer_raises_risk_when_worker_cites_no_evidence(evidence):
    worker = {"output": "Everything looks fine."}
    result = review_output({"output": "plan"}, worker, evidence, FakeLLM())
    assert result["risk_level"] == "MEDIUM"
    assert result["governance_notes"]


def test_reviewer_unknown_when_format_not_followed(evidence):
    llm = FakeLLM(reviewer_text="Looks okay to me.")
    result = review_output({"output": "plan"}, {"output": "Evidence Used: 101"}, evidence, llm)
    assert result["recommendation"] == "UNKNOWN"
