#!/bin/bash
# ASD Group 24 — setup verification script
# Run from repo root: bash scripts/test/verify-setup.sh
# Add --build to also build/test the known-working shared services (slower)

set -u
PASS=0
FAIL=0
WARN=0

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
warn() { echo "  WARN: $1"; WARN=$((WARN+1)); }

echo "============================================================"
echo "ASD Group 24 — Setup Verification"
echo "============================================================"

echo
echo "1. docker-compose.yml validity"
if docker-compose config > /dev/null 2>&1; then
    pass "docker-compose config parses without errors"
else
    fail "docker-compose config failed — run 'docker-compose config' to see the error"
fi

echo
echo "2. Folder structure — each feature has three Dockerfiles"
FEATURES=(
    "1-kathrynna-appointments"
    "2-div-ehr"
    "3-william-pharmacy"
    "4-samarra-billing"
    "5-max-labtests"
    "6-brian-wardbed"
)
for feature in "${FEATURES[@]}"; do
    if [ ! -d "$feature" ]; then
        fail "$feature folder does not exist"
        continue
    fi
    for tier in frontend backend database; do
        if [ -f "$feature/$tier/Dockerfile" ]; then
            pass "$feature/$tier/Dockerfile exists"
        else
            fail "$feature/$tier/Dockerfile missing"
        fi
    done
    # A leftover top-level Dockerfile means the folder was never split
    # into frontend/backend/database properly — flag it.
    if [ -f "$feature/Dockerfile" ]; then
        fail "$feature/Dockerfile exists at top level — should not exist, only frontend/backend/database Dockerfiles are expected"
    fi
done

echo
echo "3. Shared services — full file set"
declare -A SHARED_FILES=(
    ["shared/database"]="requirements.txt init_db.py app.py Dockerfile"
    ["shared/backend"]="requirements.txt app.py Dockerfile"
    ["shared/frontend"]="Dockerfile"
)
for dir in "${!SHARED_FILES[@]}"; do
    for file in ${SHARED_FILES[$dir]}; do
        if [ -s "$dir/$file" ]; then
            pass "$dir/$file exists and is non-empty"
        elif [ -f "$dir/$file" ]; then
            warn "$dir/$file exists but is empty (0 bytes)"
        else
            fail "$dir/$file missing"
        fi
    done
done

echo
echo "4. ai-services/ai-mode — full file set (plain Python, no Dockerfile expected)"
for file in requirements.txt plan.py act.py observe.py adapt.py app.py; do
    path="ai-services/ai-mode/$file"
    if [ -s "$path" ]; then
        pass "$path exists and is non-empty"
    elif [ -f "$path" ]; then
        warn "$path exists but is empty (0 bytes)"
    else
        fail "$path missing"
    fi
done
if [ -f "ai-services/ai-mode/Dockerfile" ]; then
    warn "ai-services/ai-mode/Dockerfile exists — ai-mode is meant to run as plain Python, not containerised. Remove this file unless the team has deliberately decided to containerise it."
else
    pass "ai-services/ai-mode has no Dockerfile (expected — runs as plain Python, not part of docker-compose)"
fi

echo
echo "5. Total Dockerfile count (expected: 21 = 6 students x 3 + shared x 3)"
DOCKERFILE_COUNT=$(find . -name "Dockerfile" -not -path "./.git*" | wc -l | tr -d ' ')
if [ "$DOCKERFILE_COUNT" -eq 21 ]; then
    pass "Found exactly 21 Dockerfiles"
else
    fail "Found $DOCKERFILE_COUNT Dockerfiles, expected 21 — run 'find . -name \"Dockerfile\" -not -path \"./.git*\"' to see the full list and spot the extra/missing one"
fi

echo
echo "6. Port consistency — docker-compose.yml vs README.md"
if [ -f docker-compose.yml ] && [ -f README.md ]; then
    COMPOSE_PORTS=$(grep -oE '"[0-9]{4}:[0-9]{2,4}"' docker-compose.yml | grep -oE '^"[0-9]{4}' | tr -d '"' | sort -u)
    README_PORTS=$(grep -oE '\| [0-9]{4} \|' README.md | grep -oE '[0-9]{4}' | sort -u)
    MISSING_IN_README=$(comm -23 <(echo "$COMPOSE_PORTS") <(echo "$README_PORTS"))
    if [ -z "$MISSING_IN_README" ]; then
        pass "All docker-compose.yml ports appear in README.md"
    else
        warn "Ports in docker-compose.yml but not found in README.md (often a false positive from table formatting — verify manually): $(echo $MISSING_IN_README | tr '\n' ' ')"
    fi
else
    warn "docker-compose.yml or README.md missing — skipped port check"
fi

echo
echo "7. CI workflows — paths filter check"
if [ -d .github/workflows ]; then
    for wf in .github/workflows/*.yml; do
        name=$(basename "$wf")
        if [[ "$name" == "cloud-deployment.yml" ]] || [[ "$name" == "integration-ci.yml" ]]; then
            warn "$name — skipped (not a per-student workflow)"
            continue
        fi
        if grep -q "paths:" "$wf"; then
            pass "$name has a paths: filter"
        else
            fail "$name is missing a paths: filter — will trigger on every push"
        fi
    done
else
    fail ".github/workflows directory not found"
fi

if [ "${1:-}" == "--build" ]; then
    echo
    echo "8. Build + smoke test known-working services (this takes a minute)"
    docker build -t verify-shared-db-test shared/database > /tmp/verify-db.log 2>&1 \
        && pass "shared/database builds" || fail "shared/database build failed (see /tmp/verify-db.log)"
    docker build -t verify-shared-backend-test shared/backend > /tmp/verify-backend.log 2>&1 \
        && pass "shared/backend builds" || fail "shared/backend build failed (see /tmp/verify-backend.log)"
else
    echo
    echo "(skipping actual docker builds — pass --build to include them)"
fi

echo
echo "============================================================"
echo "RESULTS: $PASS passed, $WARN warnings, $FAIL failed"
echo "============================================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0