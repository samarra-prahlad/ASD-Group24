#!/bin/bash
set -e

echo "=== Ward/Bed Security Report ==="

echo
echo "=== Ruff security scan ==="
python -m ruff check \
  6-brian-wardbed/backend \
  6-brian-wardbed/database \
  --select S

echo
echo "=== detect-secrets ==="
python -m detect_secrets scan 6-brian-wardbed

echo
echo "=== pip-audit ==="
python -m pip_audit \
  -r 6-brian-wardbed/backend/requirements.txt \
  -r 6-brian-wardbed/database/requirements.txt

echo
echo "=== All Ward/Bed security checks passed ==="