"""Helpers shared by the Planner, Worker and Reviewer agents."""
import json
import os

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def load_prompt(name):
    with open(os.path.join(PROMPTS_DIR, name), encoding="utf-8") as f:
        return f.read().strip()


def evidence_block(evidence, max_records, max_chars):
    shown = evidence[:max_records]
    text = json.dumps(shown, indent=2, default=str)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... (truncated)"
    note = f"{len(evidence)} record(s) supplied"
    if len(evidence) > len(shown):
        note += f", first {len(shown)} shown"
    return f"{note}\n{text}"


def evidence_ids(evidence):
    """Values of 'id' / '*_id' fields, used to check the Worker actually cites the evidence."""
    ids = set()
    for record in evidence:
        if isinstance(record, dict):
            for key, value in record.items():
                if (key == "id" or key.endswith("_id")) and value not in (None, ""):
                    ids.add(str(value))
    return ids


def step_result(model, text, error, **extra):
    if error:
        return {"status": "failed", "model": model, "output": None, "error": error, **extra}
    return {"status": "completed", "model": model, "output": text, "error": None, **extra}
