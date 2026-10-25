"""Release 2 review modes for the Group 24 shared agentic loop.

Three modes, each following OBSERVE -> ACT -> ADAPT (review) -> human decision:
  multi-agent : reviews the shared Multi-Agent Server and its workflow/audit evidence
  testing     : reviews every feature's pre-commit security setup and post-commit CI endpoint tests
  cloud       : reviews the Azure deployment scripts/workflow and the deployment results

OBSERVE collects evidence from the repository (and the running Multi-Agent Server).
ACT    : qwen2.5:0.5b writes an assessment (Strengths / Weaknesses / Recommendations).
REVIEW : llama3.1:8b validates that assessment against the same evidence.
"""
import glob
import json
import os
import re

import requests

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
IMPLEMENTATION_MODEL = os.getenv("LOOP_IMPLEMENTATION_MODEL", "qwen2.5:0.5b")
REVIEW_MODEL = os.getenv("LOOP_REVIEW_MODEL", "llama3.1:8b")
MULTI_AGENT_SERVER_URL = os.getenv("MULTI_AGENT_SERVER_URL", "http://localhost:7002")
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "300"))

FEATURES = [
    "1-kathrynna-appointments", "2-div-ehr", "3-william-pharmacy",
    "4-samarra-billing", "5-max-labtests", "6-brian-wardbed",
]

PROMPTS = {
    "multi-agent": {
        "scope": "Release 2 Multi-Agent Workflow (Planner -> Worker -> Reviewer -> Human Review)",
        "implementation": (
            "Review the Group 24 Multi-Agent Server and workflow evidence.\n"
            "Evaluate: agent roles and sequencing, evidence grounding, human-review gating, "
            "audit/workflow logging, and feature integration.\n"
            "Return:\nStrengths:\nWeaknesses:\nRecommendations:\nMaximum 60 words."
        ),
        "review": (
            "Validate the multi-agent assessment against the evidence.\n"
            "Identify gaps or risks in agent sequencing, evidence grounding, or human approval gating.\n"
            "Reply in at most 40 words and stay evidence-based."
        ),
    },
    "testing": {
        "scope": "Release 2 Testing: pre-commit security scans and post-commit CI/CD endpoint tests",
        "implementation": (
            "Review the Group 24 testing evidence.\n"
            "Evaluate: pre-commit scan coverage (Ruff security rules, detect-secrets, pip-audit), "
            "security findings, post-commit endpoint test coverage (two endpoints per feature), and evidence completeness.\n"
            "Return:\nStrengths:\nWeaknesses:\nRecommendations:\nMaximum 60 words."
        ),
        "review": (
            "Validate the testing assessment against the evidence.\n"
            "Identify gaps or risks in scan coverage, commit blocking, endpoint test coverage, or missing evidence per feature.\n"
            "Reply in at most 40 words and stay evidence-based."
        ),
    },
    "cloud": {
        "scope": "Release 2 Azure Cloud Deployment",
        "implementation": (
            "Review the Group 24 Azure Container Apps deployment evidence.\n"
            "Evaluate: OIDC/managed identity, ingress isolation (internal vs external), AI services disabled, "
            "deployment workflow validation, and deployment test results.\n"
            "Return:\nStrengths:\nRisks:\nRecommendations:\nMaximum 80 words."
        ),
        "review": (
            "Validate the deployment assessment against the evidence.\n"
            "Identify gaps or risks in managed identity, ingress isolation, AI services being disabled, "
            "or deployment validation. State whether the evidence supports release.\n"
            "Reply in at most 40 words and stay evidence-based."
        ),
    },
}


# ---------------------------------------------------------------- helpers
def _path(*parts):
    return os.path.join(REPO_ROOT, *parts)


def _read(*parts):
    try:
        with open(_path(*parts), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _exists(*parts):
    return os.path.exists(_path(*parts))


def _jsonl(*parts):
    records = []
    for line in _read(*parts).splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except ValueError:
                pass
    return records


def call_llm(model, system_prompt, user_prompt):
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/chat/completions",
            json={"model": model, "temperature": 0.2, "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]},
            timeout=LLM_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:  # report the failure in the log instead of crashing the loop
        return f"MODEL FAILED: {exc}"


# ---------------------------------------------------------------- OBSERVE collectors
def observe_multi_agent():
    lines = []
    server = "multi-agent-server"
    required = ["app.py", "coordinator.py", "store.py", "llm_client.py", "workflow_runner.py",
                "agents/planner_agent.py", "agents/worker_agent.py", "agents/reviewer_agent.py",
                "prompts/planner_prompt.txt", "prompts/worker_prompt.txt", "prompts/reviewer_prompt.txt"]
    missing = [f for f in required if not _exists(server, f)]
    lines.append(f"multi-agent-server files: {len(required) - len(missing)}/{len(required)} present"
                 + (f" (missing: {', '.join(missing)})" if missing else ""))

    coordinator = _read(server, "coordinator.py")
    calls = [fn for fn in ("plan_workflow", "generate_output", "review_output") if fn in coordinator]
    lines.append(f"coordinator wires agents in order: {', '.join(calls)} ({len(calls)}/3)")
    decisions = re.findall(r'"(approve|partially_accept|correct|reject)"', coordinator)
    lines.append(f"human decisions supported: {', '.join(sorted(set(decisions)))}")

    try:
        health = requests.get(f"{MULTI_AGENT_SERVER_URL}/health", timeout=5).json()
        lines.append(f"live server /health: status={health.get('status')}, models={health.get('models')}")
    except Exception as exc:
        lines.append(f"live server /health: unreachable ({type(exc).__name__})")

    audit = _jsonl(server, "coordination_audit.jsonl")
    history = _jsonl(server, "workflow_history.jsonl")
    started = sum(1 for e in audit if e.get("event") == "workflow_started")
    failed = sum(1 for e in audit if e.get("event") == "workflow_failed")
    human = [e for e in audit if e.get("event") == "human_decision"]
    risks = [e.get("risk_level") for e in audit if e.get("event") == "awaiting_human_review"]
    lines.append(f"coordination_audit.jsonl: {len(audit)} events, {started} workflows started, {failed} failed, "
                 f"{len(human)} human decisions")
    if human:
        counts = {}
        for e in human:
            counts[e.get("decision")] = counts.get(e.get("decision"), 0) + 1
        lines.append(f"human decisions recorded: {counts}")
    if risks:
        lines.append(f"reviewer risk levels: {{'LOW': {risks.count('LOW')}, 'MEDIUM': {risks.count('MEDIUM')}, "
                     f"'HIGH': {risks.count('HIGH')}}}")
    latest = {}
    for snapshot in history:
        latest[snapshot.get("workflow_id")] = snapshot
    features = sorted({w.get("feature") for w in latest.values() if w.get("feature")})
    lines.append(f"workflow_history.jsonl: {len(latest)} workflows, features used: {', '.join(features) or 'none'}")
    if latest:
        last = list(latest.values())[-1]
        reviewer = (last.get("steps") or {}).get("reviewer") or {}
        lines.append(f"latest workflow {last.get('workflow_id')}: feature={last.get('feature')}, "
                     f"status={last.get('status')}, risk={reviewer.get('risk_level')}, "
                     f"evidence_count={last.get('evidence_count')}")

    integrated = []
    for feature in FEATURES:
        files = glob.glob(_path(feature, "backend", "**", "*.py"), recursive=True)
        if any("MULTI_AGENT_SERVER_URL" in open(f, encoding="utf-8", errors="ignore").read() for f in files):
            integrated.append(feature)
    lines.append(f"feature backends calling the Multi-Agent Server: {len(integrated)}/6 ({', '.join(integrated)})")
    return lines


def observe_testing():
    lines = []
    for feature in FEATURES:
        config = _read(feature, ".pre-commit-config.yaml")
        # The brief allows approved equivalents: bandit for Ruff S rules, gitleaks for detect-secrets.
        hooks = [name for name, keys in (("ruff/bandit", ("ruff", "bandit")),
                                         ("detect-secrets/gitleaks", ("detect-secrets", "gitleaks")),
                                         ("pip-audit", ("pip-audit",)))
                 if any(k in config for k in keys)]
        ruff_cfg = _read(feature, "ruff.toml")
        baseline = _read(feature, ".secrets.baseline")
        secrets_count = "n/a"
        if baseline:
            try:
                secrets_count = sum(len(v) for v in json.loads(baseline).get("results", {}).values())
            except ValueError:
                secrets_count = "unreadable"
        reports = (glob.glob(_path("docs", "release-2", "*", "*")) + glob.glob(_path(feature, "*security*report*"))
                   + glob.glob(_path(feature, "*SECURITY*")) + glob.glob(_path(feature, "*", "*SECURITY*")))
        short = feature.split("-", 2)[-1]
        has_report = any(short[:5] in r.lower() or feature in r for r in reports)

        workflow = ""
        for wf in glob.glob(_path(".github", "workflows", f"{feature.split('-')[0]}-*.yml")):
            workflow = open(wf, encoding="utf-8").read()
        test_files = [f for f in glob.glob(_path(feature, "tests", "*.py"))
                      if any(k in os.path.basename(f) for k in ("endpoint", "release2", "release_2"))]
        endpoint_tests = 0
        referenced = False
        for f in test_files:
            endpoint_tests += len(re.findall(r"^def test_", open(f, encoding="utf-8").read(), re.M))
            referenced = referenced or os.path.basename(f) in workflow or "tests/" in workflow
        lines.append(
            f"{feature}: pre-commit hooks [{', '.join(hooks) or 'NONE'}], ruff S rules={'yes' if 'S' in ruff_cfg else ('bandit' if 'bandit' in config else 'no')}, "
            f"secrets baseline={secrets_count}, scan report={'yes' if has_report else 'no'} | "
            f"CI endpoint tests: {endpoint_tests} in {len(test_files)} file(s), run by workflow={'yes' if referenced and test_files else 'no'}"
        )
    return lines


def observe_cloud():
    lines = []
    scripts = ["services.sh", "gh-secrets-setup.sh", "env-setup.sh", "build-images.sh",
               "deploy-azure-env.sh", "deploy-azure.sh", "deployment-testing.sh", "cleanup.sh"]
    present = [s for s in scripts if _exists("scripts", "cloud", s)]
    lines.append(f"scripts/cloud: {len(present)}/{len(scripts)} reusable scripts present")

    deploy = _read("scripts", "cloud", "deploy-azure.sh")
    lines.append(f"deploy-azure.sh: internal ingress={'--ingress' in deploy and 'internal' in deploy}, "
                 f"external ingress={'external' in deploy}, managed identity for ACR pull={'--registry-identity' in deploy}, "
                 f"AI flags false={'MULTI_AGENT_ENABLED=false' in deploy}")

    wf = _read(".github", "workflows", "cloud-deployment.yml")
    lines.append(f"cloud-deployment.yml: OIDC (id-token: write)={'id-token: write' in wf}, azure/login={'azure/login' in wf}, "
                 f"deploy gated on validation (needs: [validate])={'needs: [validate]' in wf}, "
                 f"smoke test={'Smoke test' in wf}, deployment testing={'deployment-testing.sh' in wf}")

    results = _read("reports", "cloud", "deployment-results.md")
    if results:
        result = re.search(r"Result:\*\*\s*(.+)", results)
        entry = re.search(r"Entry point:\*\*\s*(\S+)", results)
        tested = re.search(r"Tested at \(UTC\):\*\*\s*(\S+)", results)
        fails = results.count("| FAIL |")
        ai_rows = len(re.findall(r"AI services \| ENV .*\| disabled \| disabled \| PASS", results))
        status = re.search(r"Status:\s*(.+)", results)
        lines.append(f"deployment-results.md: {result.group(1).strip() if result else 'no result line'}, "
                     f"{fails} failed checks, AI-disabled checks passed={ai_rows}, "
                     f"tested at {tested.group(1) if tested else '?'}")
        lines.append(f"entry point: {entry.group(1) if entry else '?'}")
        lines.append(f"current release decision line: {status.group(1).strip() if status else 'missing'}")
    else:
        lines.append("deployment-results.md: MISSING (download the cloud-deployment-evidence artifact)")
    return lines


OBSERVERS = {"multi-agent": observe_multi_agent, "testing": observe_testing, "cloud": observe_cloud}


# ---------------------------------------------------------------- run one review mode
def run_review_mode(mode):
    prompts = PROMPTS[mode]
    print(f"OBSERVE ({prompts['scope']})")
    evidence = OBSERVERS[mode]()
    for line in evidence:
        print(f"  Checked {line}")
    evidence_text = "\n".join(f"- {line}" for line in evidence)

    print()
    print(f"ACT (implementation assessment, {IMPLEMENTATION_MODEL})")
    implementation = call_llm(
        IMPLEMENTATION_MODEL,
        "You are a precise software reviewer. Use only the supplied evidence.",
        f"{prompts['implementation']}\n\nReview Scope:\n{prompts['scope']}\n\nObserved Evidence:\n{evidence_text}",
    )
    print(implementation)

    print()
    print(f"REVIEW (validation, {REVIEW_MODEL})")
    review = call_llm(
        REVIEW_MODEL,
        prompts["review"],
        f"Implementation Recommendation:\n{implementation}\n\nObserved Evidence:\n{evidence_text}",
    )
    print(review)
    return evidence
