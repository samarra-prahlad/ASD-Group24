"""Coordinates Planner -> Worker -> Reviewer, then gates the result on a human decision."""
import copy
import uuid

from agents.planner_agent import plan_workflow
from agents.reviewer_agent import review_output
from agents.worker_agent import generate_output
from store import now_iso

AWAITING = "awaiting_human_review"
DECISIONS = {
    "approve": "approved",
    "partially_accept": "partially_approved",
    "correct": "corrected",
    "reject": "rejected",
}


class WorkflowNotFound(Exception):
    pass


class InvalidDecision(Exception):
    pass


class WorkflowStateError(Exception):
    pass


class Coordinator:
    def __init__(self, llm, store):
        self.llm = llm
        self.store = store

    def _save(self, workflow):
        workflow["updated_at"] = now_iso()
        self.store.save(workflow)

    def run(self, user_request, feature="general", evidence=None, requested_by=None):
        evidence = evidence or []
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        workflow = {
            "workflow_id": workflow_id,
            "feature": feature,
            "user_request": user_request,
            "requested_by": requested_by,
            "created_at": now_iso(),
            "status": "running",
            "evidence_count": len(evidence),
            "steps": {},
            "human_review": None,
            "final_output": None,
        }
        self._save(workflow)
        self.store.audit(workflow_id, "workflow_started", feature=feature, evidence_count=len(evidence))

        steps = [
            ("planner", lambda: plan_workflow(user_request, feature, evidence, self.llm)),
            ("worker", lambda: generate_output(workflow["steps"]["planner"], user_request, evidence, self.llm)),
            ("reviewer", lambda: review_output(workflow["steps"]["planner"], workflow["steps"]["worker"],
                                               evidence, self.llm)),
        ]
        for name, call in steps:
            self.store.audit(workflow_id, "agent_started", agent=name)
            result = call()
            workflow["steps"][name] = result
            if result["status"] != "completed":
                self.store.audit(workflow_id, "agent_failed", agent=name, error=result["error"])
                workflow["status"] = "failed"
                self._save(workflow)
                self.store.audit(workflow_id, "workflow_failed", failed_agent=name)
                return copy.deepcopy(workflow)
            self.store.audit(workflow_id, "agent_completed", agent=name, model=result["model"])
            self._save(workflow)

        reviewer = workflow["steps"]["reviewer"]
        workflow["status"] = AWAITING
        self._save(workflow)
        self.store.audit(workflow_id, "awaiting_human_review",
                         risk_level=reviewer.get("risk_level"), recommendation=reviewer.get("recommendation"))
        return copy.deepcopy(workflow)

    def review(self, workflow_id, decision, reviewer, notes="", correction=None):
        workflow = self.store.get(workflow_id)
        if workflow is None:
            raise WorkflowNotFound(workflow_id)
        if decision not in DECISIONS:
            raise InvalidDecision(f"decision must be one of: {', '.join(DECISIONS)}")
        if decision == "correct" and not (correction and str(correction).strip()):
            raise InvalidDecision("a correction is required when decision is 'correct'")
        if not reviewer or not str(reviewer).strip():
            raise InvalidDecision("reviewer is required")
        if workflow["status"] != AWAITING:
            raise WorkflowStateError(f"workflow is '{workflow['status']}', not awaiting human review")

        worker_output = workflow["steps"]["worker"]["output"]
        workflow["human_review"] = {
            "decision": decision,
            "reviewer": reviewer,
            "notes": notes or "",
            "correction": correction,
            "decided_at": now_iso(),
        }
        workflow["final_output"] = {
            "approve": worker_output,
            "partially_accept": worker_output,
            "correct": correction,
            "reject": None,
        }[decision]
        workflow["status"] = DECISIONS[decision]
        self._save(workflow)
        self.store.audit(workflow_id, "human_decision", decision=decision, reviewer=reviewer,
                         final_status=workflow["status"])
        return copy.deepcopy(workflow)

    def get(self, workflow_id):
        return self.store.get(workflow_id)

    def list(self, feature=None, limit=20):
        return self.store.list(feature=feature, limit=limit)
