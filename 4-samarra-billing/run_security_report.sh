#!/bin/bash
# Generates the Feature 4 (Billing) pre-commit security evidence file.
# Run from the repository root:  bash 4-samarra-billing/run_security_report.sh
set -u
OUT=docs/release-2/billing/precommit-security-report.txt
TMP=$(mktemp)
mkdir -p docs/release-2/billing
# Write to a temp file first so the hooks don't see a tracked file changing mid-run.
{
  echo "Feature 4 (Billing & Insurance) - pre-commit security scan report"
  echo "Generated : $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Commit    : $(git rev-parse --short HEAD) on branch $(git rev-parse --abbrev-ref HEAD)"
  echo "Tools     : ruff $(ruff --version | awk '{print $2}'), detect-secrets $(detect-secrets --version), pip-audit $(pip-audit --version | awk '{print $2}')"
  echo
  echo "=== Hooks (pre-commit, all files under 4-samarra-billing/) ==="
  pre-commit run --all-files -c 4-samarra-billing/.pre-commit-config.yaml --verbose
  echo
  echo "=== Ruff security rule summary (flake8-bandit S) ==="
  ruff check --config 4-samarra-billing/ruff.toml --statistics 4-samarra-billing && echo "No security findings."
  echo
  echo "=== pip-audit (backend and database requirements) ==="
  pip-audit -r 4-samarra-billing/backend/requirements.txt -r 4-samarra-billing/database/requirements.txt
  echo
  echo "=== detect-secrets baseline ==="
  echo "Baseline file: 4-samarra-billing/.secrets.baseline ($(python3 -c "import json;print(sum(len(v) for v in json.load(open('4-samarra-billing/.secrets.baseline'))['results'].values()))") secrets recorded)"
  echo
  echo "=== Fixes made to pass the scans ==="
  echo "- Flask debug mode now off unless FLASK_DEBUG=1 (Ruff S201, backend + database)"
  echo "- host=0.0.0.0 kept with justification: services must listen on all interfaces in their containers (Ruff S104)"
  echo "- Upgraded flask 3.0.3 -> 3.1.3, requests 2.32.3 -> 2.33.0, flask-cors 4.0.1 -> 6.0.0 (pip-audit CVEs)"
} 2>&1 | grep -v "cachecontrol" | tee "$TMP"
cp "$TMP" "$OUT"
rm -f "$TMP"
echo
echo "Saved to $OUT"
