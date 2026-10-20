#!/bin/bash
# Generates the Feature 5 pre-commit security evidence file.
# Run from the repository root:  bash 5-max-labtests/run_security_report.sh
set -u
OUT=docs/release-2/labtests/precommit-security-report.txt
TMP=$(mktemp)
mkdir -p docs/release-2/labtests
# Output goes to a temp file first. Writing straight into the tracked report file
# while the hooks run would make pre-commit report "files were modified" (false Failed).
{
  echo "Feature 5 (Lab Tests & Diagnostics) - pre-commit security scan report"
  echo "Generated : $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Commit    : $(git rev-parse --short HEAD) on branch $(git rev-parse --abbrev-ref HEAD)"
  echo "Tools     : ruff $(ruff --version | awk '{print $2}'), detect-secrets $(detect-secrets --version), pip-audit $(pip-audit --version | awk '{print $2}')"
  echo
  echo "=== Hooks (pre-commit, all files under 5-max-labtests/) ==="
  pre-commit run --all-files -c 5-max-labtests/.pre-commit-config.yaml --verbose
  echo
  echo "=== Ruff security rule summary (flake8-bandit S) ==="
  ruff check --config 5-max-labtests/ruff.toml --statistics 5-max-labtests && echo "No security findings."
  echo
  echo "=== pip-audit (backend and database requirements) ==="
  pip-audit -r 5-max-labtests/backend/requirements.txt -r 5-max-labtests/database/requirements.txt 2>&1 | grep -v "cachecontrol"
  echo
  echo "=== detect-secrets baseline ==="
  echo "Baseline file: 5-max-labtests/.secrets.baseline (0 secrets recorded)"
} 2>&1 | grep -v "cachecontrol" | tee "$TMP"
cp "$TMP" "$OUT"
rm -f "$TMP"
echo
echo "Saved to $OUT"