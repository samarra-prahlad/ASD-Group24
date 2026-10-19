"""Terminal client: runs a Planner -> Worker -> Reviewer workflow, then records the human decision."""
import argparse
import json
import os
import sys

import requests

DEFAULT_URL = os.getenv("MULTI_AGENT_SERVER_URL", "http://localhost:7002")
HERE = os.path.dirname(os.path.abspath(__file__))
DECISIONS = ["approve", "partially_accept", "correct", "reject"]


def print_step(name, step):
    print(f"\n--- {name.upper()} [{step.get('status')}] model={step.get('model')}")
    if step.get("error"):
        print(f"ERROR: {step['error']}")
    if step.get("output"):
        print(step["output"])
    if name == "reviewer" and step.get("status") == "completed":
        print(f"\nRisk level: {step.get('risk_level')} | Recommendation: {step.get('recommendation')}")
        print(f"Grounding: {step.get('grounding')}")
        for note in step.get("governance_notes", []):
            print(f"Governance: {note}")


def main():
    parser = argparse.ArgumentParser(description="Run a multi-agent workflow from the terminal")
    parser.add_argument("--server", default=DEFAULT_URL)
    parser.add_argument("--feature", default="billing")
    parser.add_argument("--request", default="Summarise the outstanding invoices for patient 1 and flag anything unusual.")
    parser.add_argument("--evidence-file", default=os.path.join(HERE, "sample_evidence", "billing.json"))
    parser.add_argument("--decision", choices=DECISIONS, help="skip the interactive prompt")
    parser.add_argument("--reviewer", default=os.getenv("USER", "human-reviewer"))
    parser.add_argument("--notes", default="")
    parser.add_argument("--correction")
    args = parser.parse_args()

    with open(args.evidence_file, encoding="utf-8") as f:
        evidence = json.load(f)

    print(f"Running multi-agent workflow on {args.server} (this can take a minute)...")
    try:
        response = requests.post(f"{args.server}/workflow", json={
            "feature": args.feature, "user_request": args.request,
            "evidence": evidence, "requested_by": args.reviewer,
        }, timeout=600)
    except requests.exceptions.RequestException as exc:
        print(f"Could not reach the multi-agent server: {exc}")
        return 1

    workflow = response.json()
    print(f"\nWorkflow ID: {workflow.get('workflow_id')}  Status: {workflow.get('status')}")
    for name in ("planner", "worker", "reviewer"):
        if name in workflow.get("steps", {}):
            print_step(name, workflow["steps"][name])
    if response.status_code != 201:
        return 1

    decision, notes, correction = args.decision, args.notes, args.correction
    if not decision:
        while decision not in DECISIONS:
            decision = input(f"\nHuman decision [{'/'.join(DECISIONS)}]: ").strip()
        notes = input("Reviewer notes (optional): ").strip()
    if decision == "correct" and not correction:
        correction = input("Corrected output: ").strip()

    review = requests.post(f"{args.server}/workflow/{workflow['workflow_id']}/review", json={
        "decision": decision, "reviewer": args.reviewer, "notes": notes, "correction": correction,
    }, timeout=30)
    result = review.json()
    if review.status_code != 200:
        print(f"Review rejected: {result.get('error')}")
        return 1
    print(f"\nHuman decision recorded: {decision} -> status {result['status']}")
    print("Logged to workflow_history.jsonl and coordination_audit.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
