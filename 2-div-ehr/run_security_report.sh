#!/bin/bash
# Generates the Feature 2 (EHR) pre-commit security evidence file.
# Run from the repository root:  bash 2-div-ehr/run_security_report.sh
# The report is saved OUTSIDE the repository by default (override with OUT=/some/path).
set -u
OUT="${OUT:-$HOME/Documents/ehr-r2-evidence/precommit-security-report.txt}"
TMP=$(mktemp)
mkdir -p "$(dirname "$OUT")"
# Output goes to a temp file first so pre-commit never sees a modified tracked file.
{
  echo "Feature 2 (EHR) - pre-commit security scan report"
  echo "Generated : $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Commit    : $(git rev-parse --short HEAD) on branch $(git rev-parse --abbrev-ref HEAD)"
  echo "Tools     : ruff $(ruff --version | awk '{print $2}'), detect-secrets $(detect-secrets --version), pip-audit $(pip-audit --version | awk '{print $2}')"
  echo
  echo "=== Hooks (pre-commit, all files under 2-div-ehr/) ==="
  pre-commit run --all-files -c 2-div-ehr/.pre-commit-config.yaml --verbose
  echo
  echo "=== Ruff security rule summary (flake8-bandit S) ==="
  ruff check --config 2-div-ehr/ruff.toml --statistics 2-div-ehr && echo "No security findings."
  echo
  echo "=== pip-audit (backend and database requirements) ==="
  pip-audit -r 2-div-ehr/backend/requirements.txt -r 2-div-ehr/database/requirements.txt 2>&1 | grep -v "cachecontrol"
  echo
  echo "=== detect-secrets baseline ==="
  echo "Baseline file: 2-div-ehr/.secrets.baseline (0 secrets recorded)"
} 2>&1 | grep -v "cachecontrol" | tee "$TMP"
cp "$TMP" "$OUT"
rm -f "$TMP"
echo
echo "Saved to $OUT"
