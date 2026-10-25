#!/bin/bash
# Generates the Feature 3 (Pharmacy) pre-commit security evidence file.
# Run from the repository root:  bash 3-william-pharmacy/run_security_report.sh
set -u

cd "$(git rev-parse --show-toplevel)" || exit 1

# Tools are called through Python so this works even when pip's Scripts folder isn't on PATH.
PY="${PYTHON:-python}"
FEATURE_DIR="3-william-pharmacy"
CONFIG="$FEATURE_DIR/.pre-commit-config.yaml"
OUT=docs/release-2/pharmacy/precommit-security-report.txt
TMP=$(mktemp)
mkdir -p docs/release-2/pharmacy

# Write to a temp file first so the hooks don't see a tracked file changing mid-run.
{
  echo "Feature 3 (Pharmacy) - pre-commit security scan report"
  echo "Generated : $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Commit    : $(git rev-parse --short HEAD) on branch $(git rev-parse --abbrev-ref HEAD)"
  echo "Tools     : ruff $($PY -m ruff --version | awk '{print $2}'), detect-secrets $($PY -m detect_secrets --version), pip-audit $($PY -m pip_audit --version | awk '{print $2}'), pre-commit $($PY -m pre_commit --version | awk '{print $2}')"
  echo
  echo "=== Hooks (pre-commit, all files under $FEATURE_DIR/) ==="
  $PY -m pre_commit run --all-files --color never -c "$CONFIG" --verbose
  echo
  echo "=== Ruff security rule summary (flake8-bandit S) ==="
  $PY -m ruff check --config "$FEATURE_DIR/ruff.toml" --statistics "$FEATURE_DIR" && echo "No security findings."
  echo
  echo "=== pip-audit (backend and database requirements) ==="
  $PY -m pip_audit -r "$FEATURE_DIR/backend/requirements.txt" -r "$FEATURE_DIR/database/requirements.txt"
  echo
  echo "=== detect-secrets baseline ==="
  echo "Baseline file: $FEATURE_DIR/.secrets.baseline ($($PY -c "import json;print(sum(len(v) for v in json.load(open('$FEATURE_DIR/.secrets.baseline'))['results'].values()))") secrets recorded)"
  echo
  echo "=== Accepted findings ==="
  echo "- S104 (bind to 0.0.0.0): suppressed with a reason - containers must listen on all interfaces."
  echo "- S608 x2 (database/app.py UPDATE queries): suppressed with a reason - column names come from a fixed allow-list and values are bound with '?'."
  echo "- S101 (assert) in tests: ignored by config - pytest requires assert."
  echo "- detect-secrets, backend/app.py: api_key=\"ollama\" is a placeholder Ollama ignores; allow-listed inline."
  echo "- chromadb 1.5.9 (5 advisories, no fix available): only in tests/requirements.txt, which is not deployed; excluded from the audit scope."
  echo
  echo "=== Fixed findings ==="
  echo "- Flask debug mode now off unless FLASK_DEBUG=true (Ruff S201, backend + database)"
} 2>&1 | tee "$TMP"
cp "$TMP" "$OUT"
rm -f "$TMP"
echo
echo "Saved to $OUT"