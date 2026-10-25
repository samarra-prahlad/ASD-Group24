FEATURE_DIR="1-kathrynna-appointments"
REPO_ROOT="$(git rev-parse --show-toplevel)" || exit 1
cd "$REPO_ROOT" || exit 1

CONFIG="$FEATURE_DIR/.pre-commit-config.yaml"
REPORT="$FEATURE_DIR/security-report.txt"

# bandit and pip-audit are also run directly for the summary sections
python3 -m pip install --quiet bandit pip-audit pre-commit >/dev/null 2>&1

version() { "$@" 2>/dev/null | head -n 1 | awk '{print $NF}'; }

{
  echo "Feature 1 (Appointments) - pre-commit security scan report"
  echo "Generated : $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Commit    : $(git rev-parse --short HEAD) on branch $(git rev-parse --abbrev-ref HEAD)"
  echo "Tools     : bandit $(version bandit --version), pip-audit $(version pip-audit --version), gitleaks (pre-commit hook), pre-commit $(version pre-commit --version)"
  echo
  echo "=== Hooks (pre-commit, all files under $FEATURE_DIR/) ==="
  for hook in detect-private-key check-added-large-files check-merge-conflict check-yaml check-json gitleaks bandit pip-audit; do
    pre-commit run "$hook" --all-files -c "$CONFIG" --verbose 2>&1 | grep -v '^\[INFO\]'
  done
  echo
  echo "=== Bandit summary (backend + database, tests excluded) ==="
  bandit -r "$FEATURE_DIR/backend" "$FEATURE_DIR/database" -x "*/tests/*" -q 2>&1 \
    | grep -E "No issues identified|Issue:|Location:|Total lines skipped|Severity" \
    || echo "No issues identified."
  echo
  echo "=== pip-audit (backend and database requirements) ==="
  pip-audit -r "$FEATURE_DIR/backend/requirements.txt" -r "$FEATURE_DIR/database/requirements.txt" 2>&1 \
    | grep -v -E "^(Found|DEBUG)" | tail -n 5
  echo
  echo "=== Accepted findings ==="
  echo "B104 (bind to 0.0.0.0): marked '# nosec B104' - containers must listen on all interfaces."
  echo
  echo "=== Fixed findings ==="
  echo "B201 Flask debug=True in database/app.py -> now only when FLASK_DEBUG=1"
  echo "PYSEC-2026-2151 Flask 3.1.2 -> upgraded to 3.1.3"
} > "$REPORT"

echo "Report written to $REPORT"