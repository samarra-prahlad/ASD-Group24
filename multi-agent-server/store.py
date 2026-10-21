"""Persists workflow snapshots (workflow_history.jsonl) and coordination events (coordination_audit.jsonl)."""
import copy
import json
import os
import threading
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class WorkflowStore:
    def __init__(self, data_dir):
        os.makedirs(data_dir, exist_ok=True)
        self.history_path = os.path.join(data_dir, "workflow_history.jsonl")
        self.audit_path = os.path.join(data_dir, "coordination_audit.jsonl")
        self._lock = threading.Lock()
        self._workflows = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.history_path):
            return
        with open(self.history_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    snapshot = json.loads(line)
                except ValueError:
                    continue
                if "workflow_id" in snapshot:
                    self._workflows[snapshot["workflow_id"]] = snapshot  # last snapshot wins

    def _append(self, path, record):
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    def save(self, workflow):
        with self._lock:
            self._workflows[workflow["workflow_id"]] = copy.deepcopy(workflow)
            self._append(self.history_path, workflow)

    def audit(self, workflow_id, event, **details):
        record = {"timestamp": now_iso(), "workflow_id": workflow_id, "event": event, **details}
        with self._lock:
            self._append(self.audit_path, record)

    def get(self, workflow_id):
        with self._lock:
            workflow = self._workflows.get(workflow_id)
            return copy.deepcopy(workflow) if workflow else None

    def list(self, feature=None, limit=20):
        with self._lock:
            items = [copy.deepcopy(w) for w in self._workflows.values()
                     if feature is None or w.get("feature") == feature]
        items.sort(key=lambda w: w.get("created_at", ""), reverse=True)
        return items[:limit]
