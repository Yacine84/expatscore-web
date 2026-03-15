#!/bin/bash

# -----------------------------------------------------------------------------
#  deploy.sh – ExpatScore.de Gold-Class Deployment
#  🚀 Automates content generation, integrity audit, and GitHub push.
# -----------------------------------------------------------------------------

set -e  # exit on any command failure (but we'll handle specific cases)

# --- Luxe styling helpers ----------------------------------------------------
GOLD='\033[33m'
BOLD='\033[1m'
NC='\033[0m' # No Colour
INFO="${BOLD}✨${NC}"
SUCCESS="${BOLD}✅${NC}"
ERROR="${BOLD}❌${NC}"
WARN="${BOLD}⚠️${NC}"
ROCKET="${BOLD}🚀${NC}"
HOURGLASS="${BOLD}⏳${NC}"

# --- 1. Run Python agent -----------------------------------------------------
echo -e "\n${ROCKET}  ${GOLD}Phase 1: Generating fresh content with agent.py${NC}"
if python3 agent.py; then
    echo -e "${SUCCESS}  agent.py completed successfully."
else
    echo -e "${ERROR}  agent.py failed. Aborting deployment."
    exit 1
fi

# --- 2. SEO & integrity audit ------------------------------------------------
echo -e "\n${HOURGLASS}  ${GOLD}Phase 2: Auditing required directories${NC}"
AUDIT_PASSED=true
for dir in banking insurance guides; do
    if [ ! -d "$dir" ]; then
        echo -e "${ERROR}  Directory '$dir' does not exist."
        AUDIT_PASSED=false
    elif [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
        echo -e "${ERROR}  Directory '$dir' exists but is empty."
        AUDIT_PASSED=false
    else
        echo -e "${SUCCESS}  Directory '$dir' is present and non‑empty."
    fi
done

if [ "$AUDIT_PASSED" = false ]; then
    echo -e "${ERROR}  Audit failed – one or more content directories are missing or empty."
    exit 1
fi
echo -e "${SUCCESS}  All content directories look healthy."

# --- 3. Git operations -------------------------------------------------------
echo -e "\n${ROCKET}  ${GOLD}Phase 3: Committing and pushing to GitHub${NC}"

# Stage all changes
git add .

# Check if there is anything to commit
if git diff --cached --quiet; then
    echo -e "${WARN}  No changes to commit. Deployment finished without push."
    exit 0
fi

# Create timestamped commit message
TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
COMMIT_MSG="Site Update: $TIMESTAMP"

if git commit -m "$COMMIT_MSG"; then
    echo -e "${SUCCESS}  Commit created: \"$COMMIT_MSG\""
else
    echo -e "${ERROR}  Commit failed."
    exit 1
fi

# Push to main branch
if git push origin main; then
    echo -e "${SUCCESS}  Successfully pushed to GitHub. Vercel deployment will start automatically."
else
    echo -e "${ERROR}  Push failed. Please check your remote settings."
    exit 1
fi

echo -e "\n${GOLD}${BOLD}🏆  Deployment completed – ExpatScore.de is now live!${NC}\n"