"""Worker agent: executes the plan using only the supplied evidence."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from agents.common import evidence_block, load_prompt, step_result  # noqa: E402


def generate_output(plan, user_request, evidence, llm):
    plan_text = plan.get("output") if isinstance(plan, dict) else str(plan)
    user_prompt = (
        f"Plan:\n{plan_text}\n\n"
        f"User request: {user_request}\n\n"
        f"Evidence:\n{evidence_block(evidence, config.MAX_EVIDENCE_RECORDS, config.MAX_EVIDENCE_CHARS)}"
    )
    text, error = llm(config.WORKER_MODEL, load_prompt("worker_prompt.txt"), user_prompt)
    return step_result(config.WORKER_MODEL, text, error, evidence_count=len(evidence))


if __name__ == "__main__":
    import json
    import llm_client

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(here, "sample_evidence", "billing.json")) as f:
        sample = json.load(f)
    plan = {"output": "Objective: summarise outstanding invoices.\nSteps: 1. List unpaid invoices. 2. Total the amount owed."}
    result = generate_output(plan, "Summarise outstanding invoices for patient 1.", sample, llm_client.chat)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "completed" else 1)
