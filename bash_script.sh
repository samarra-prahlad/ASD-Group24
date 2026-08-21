#!/bin/bash
# ASD 2026 - Add .gitkeep placeholders to EVERY empty folder in the repo
# Run this from the ROOT of your cloned GitHub repository.
# Git does not track empty folders, so every empty directory in the
# confirmed structure needs a placeholder file or it will not exist
# once committed/pushed/cloned.

set -e

echo "Adding placeholders across the full repository structure..."

add_gitkeep() {
  local folder="$1"
  mkdir -p "$folder"
  if [ -z "$(ls -A "$folder" 2>/dev/null)" ]; then
    touch "$folder/.gitkeep"
    echo "  Added .gitkeep -> $folder"
  fi
}

# ---------- Feature folders (frontend/backend/database/tests) ----------
FEATURE_FOLDERS=(
  "1-kathrynna-appointments"
  "2-div-ehr"
  "3-william-pharmacy"
  "4-samarra-billing"
  "5-max-labtests"
)

for folder in "${FEATURE_FOLDERS[@]}"; do
  add_gitkeep "$folder/frontend"
  add_gitkeep "$folder/backend"
  add_gitkeep "$folder/database"
  add_gitkeep "$folder/tests"
done

# ---------- 6-brian-shared (different shape) ----------
add_gitkeep "6-brian-shared/frontend/css"
add_gitkeep "6-brian-shared/frontend/js"
add_gitkeep "6-brian-shared/frontend/assets"
add_gitkeep "6-brian-shared/configuration"
add_gitkeep "6-brian-shared/backend"
add_gitkeep "6-brian-shared/database"
add_gitkeep "6-brian-shared/tests"
mkdir -p 6-brian-shared/frontend
if [ ! -f "6-brian-shared/frontend/index.html" ]; then
  touch "6-brian-shared/frontend/index.html"
  echo "  Restored 6-brian-shared/frontend/index.html"
fi

# ---------- ai-services ----------
add_gitkeep "ai-services/mcp-server"
add_gitkeep "ai-services/rag-server"
add_gitkeep "ai-services/multi-agent-server"
mkdir -p ai-services/ai-mode
for f in app.py plan.py act.py observe.py adapt.py Dockerfile README.md; do
  if [ ! -f "ai-services/ai-mode/$f" ]; then
    touch "ai-services/ai-mode/$f"
    echo "  Restored ai-services/ai-mode/$f"
  fi
done

# ---------- docs ----------
add_gitkeep "docs/architecture"
add_gitkeep "docs/reports"
add_gitkeep "docs/release-0"
add_gitkeep "docs/release-1"
add_gitkeep "docs/release-2"

# ---------- scripts ----------
add_gitkeep "scripts/build"
add_gitkeep "scripts/test"
add_gitkeep "scripts/deploy"

echo ""
echo "Done. Review with 'git status', then commit:"
echo "  git add ."
echo "  git commit -m \"Add .gitkeep placeholders across full repo structure\""
echo "  git push origin main"