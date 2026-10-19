"""Reviewer agent: reviews the Worker output against the plan and evidence, rates risk, recommends."""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from agents.common import evidence_block, evidence_ids, load_prompt, step_result  # noqa: E402

RISK_RE = re.compile(r"risk\s*(?:level)?\s*[:\-]?\s*\**\s*(low|medium|high)", re.IGNORECASE)
RECOMMENDATION_RE = re.compile(r"recommendation\s*[:\-]?\s*\**\s*(approve|revise|reject)", re.IGNORECASE)


def _match(pattern, text):
    found = pattern.search(text or "")
    return found.group(1).upper() if found else None


def review_output(plan, worker_result, evidence, llm):
    plan_text = plan.get("output") if isinstance(plan, dict) else str(plan)
    worker_text = (worker_result.get("output") if isinstance(worker_result, dict) else str(worker_result)) or ""

    ids = evidence_ids(evidence)
    cited = sorted(i for i in ids if re.search(rf"\b{re.escape(i)}\b", worker_text))
    grounding = {"evidence_ids_available": len(ids), "evidence_ids_cited": len(cited)}

    user_prompt = (
        f"Plan:\n{plan_text}\n\n"
        f"Worker output:\n{worker_text}\n\n"
        f"Evidence:\n{evidence_block(evidence, config.MAX_EVIDENCE_RECORDS, config.MAX_EVIDENCE_CHARS)}"
    )
    text, error = llm(config.REVIEWER_MODEL, load_prompt("reviewer_prompt.txt"), user_prompt)
    if error:
        return step_result(config.REVIEWER_MODEL, None, error, risk_level=None,
                           recommendation=None, grounding=grounding, governance_notes=[])

    risk = _match(RISK_RE, text) or "UNKNOWN"
    recommendation = _match(RECOMMENDATION_RE, text) or "UNKNOWN"
    notes = []
    # Deterministic guardrail: evidence was supplied but the Worker cited none of it.
    if ids and not cited and risk in ("LOW", "UNKNOWN"):
        risk = "MEDIUM"
        notes.append("Worker output does not cite any evidence IDs; risk raised to MEDIUM.")

    return step_result(config.REVIEWER_MODEL, text, None, risk_level=risk,
                       recommendation=recommendation, grounding=grounding, governance_notes=notes)


if __name__ == "__main__":
    import json
    import llm_client

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "sample_evidence", "billing.json")) as f:
        sample = json.load(f)
    plan = {"output": "Objective: summarise outstanding invoices."}
    worker = {"output": "Invoice 101 is pending with 50.00 owed. Evidence Used: 101"}
    result = review_output(plan, worker, sample, llm_client.chat)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "completed" else 1)
