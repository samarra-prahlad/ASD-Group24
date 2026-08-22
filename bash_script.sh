
/














Scaffold repo structure · SH
#!/bin/bash
# ASD 2026 - Release 0 Repository Scaffold (6-student team, revised)
# Run this from the ROOT of your cloned GitHub repository (or a test folder).
#
# REVISED STRUCTURE:
#   shared/ is now its own top-level folder (exclusive, not owned by any
#   single student) - contains the unified home page, css/js/assets, and
#   configuration.
#
#   6-brian-TBD is a full feature folder, same shape as the other 5
#   students (frontend/backend/database/tests) - feature name to be
#   finalised, folder name updated once decided.
#
#   Folders: 1-kathrynna-appointments, 2-div-ehr, 3-william-pharmacy,
#            4-samarra-billing, 5-max-labtests, 6-brian-TBD
 
set -e
 
echo "Scaffolding project repository structure..."
 
# ---------- Root files ----------
touch README.md
touch .gitignore
touch docker-compose.yml
 
# ---------- .github/workflows ----------
mkdir -p .github/workflows
touch .github/workflows/1-kathrynna-appointments-ci.yml
touch .github/workflows/2-div-ehr-ci.yml
touch .github/workflows/3-william-pharmacy-ci.yml
touch .github/workflows/4-samarra-billing-ci.yml
touch .github/workflows/5-max-labtests-ci.yml
touch .github/workflows/6-brian-TBD-ci.yml
touch .github/workflows/integration-ci.yml
touch .github/workflows/cloud-deployment.yml   # Release 2 only, safe to add now
 
# ---------- docs ----------
mkdir -p docs/architecture
mkdir -p docs/reports
mkdir -p docs/release-0
mkdir -p docs/release-1
mkdir -p docs/release-2
 
# ---------- shared/ (exclusive top-level folder, not owned by any student) ----------
mkdir -p shared/frontend/css
mkdir -p shared/frontend/js
mkdir -p shared/frontend/assets
mkdir -p shared/configuration
touch shared/frontend/index.html
touch shared/frontend/css/.gitkeep
touch shared/frontend/js/.gitkeep
touch shared/frontend/assets/.gitkeep
touch shared/configuration/.gitkeep
 
# ---------- All 6 student folders (identical layout, incl. Brian) ----------
FEATURE_FOLDERS=(
  "1-kathrynna-appointments"
  "2-div-ehr"
  "3-william-pharmacy"
  "4-samarra-billing"
  "5-max-labtests"
  "6-brian-TBD"
)
 
for folder in "${FEATURE_FOLDERS[@]}"; do
  mkdir -p "$folder/frontend"
  mkdir -p "$folder/backend"
  mkdir -p "$folder/database"
  mkdir -p "$folder/tests"
  touch "$folder/frontend/.gitkeep"
  touch "$folder/backend/.gitkeep"
  touch "$folder/database/.gitkeep"
  touch "$folder/tests/.gitkeep"
  touch "$folder/Dockerfile"
  touch "$folder/README.md"
done
 
# ---------- ai-services/ (single shared agentic loop) ----------
mkdir -p ai-services/ai-mode
touch ai-services/ai-mode/app.py
touch ai-services/ai-mode/plan.py
touch ai-services/ai-mode/act.py
touch ai-services/ai-mode/observe.py
touch ai-services/ai-mode/adapt.py
touch ai-services/ai-mode/Dockerfile
touch ai-services/ai-mode/README.md
 
# Placeholders for later releases (kept empty, added now for visibility)
mkdir -p ai-services/mcp-server
mkdir -p ai-services/rag-server
mkdir -p ai-services/multi-agent-server
touch ai-services/mcp-server/.gitkeep
touch ai-services/rag-server/.gitkeep
touch ai-services/multi-agent-server/.gitkeep
 
# ---------- scripts/ ----------
mkdir -p scripts/build
mkdir -p scripts/test
mkdir -p scripts/deploy
touch scripts/build/.gitkeep
touch scripts/test/.gitkeep
touch scripts/deploy/.gitkeep
 
echo "Done. Structure created."
echo ""
echo "NOTE: rename '6-brian-TBD' (folder + workflow file) once the 6th"
echo "feature is finalised, e.g.:"
echo "  git mv 6-brian-TBD 6-brian-<feature>"
echo "  git mv .github/workflows/6-brian-TBD-ci.yml .github/workflows/6-brian-<feature>-ci.yml"
 
