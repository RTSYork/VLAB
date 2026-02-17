#!/bin/bash
#
# Push VLAB board status to the embs GitHub Pages site.
# Runs on pegasus via cron every 15 minutes.
#
# Requires:
#   - Deploy key at /opt/VLAB/.ssh/embs_deploy_key (with write access)
#   - Working directory at /opt/VLAB/embs-status-repo/ (git init + remote add origin)
#
# Cron entry:
#   */15 * * * * /opt/VLAB/scripts/update_site_status.sh >> /opt/VLAB/log/status_update.log 2>&1

set -euo pipefail

REPO_DIR="/opt/VLAB/embs-status-repo"
DEPLOY_KEY="/opt/VLAB/.ssh/embs_deploy_key"
API_URL="http://localhost:9000/api/boards"
BRANCH="status-data"

GIT_SSH="ssh -i ${DEPLOY_KEY} -o StrictHostKeyChecking=accept-new"
export GIT_SSH_COMMAND="${GIT_SSH}"

echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting status update"

# Fetch board data from the web dashboard API
RAW=$(curl -sf --max-time 10 "${API_URL}") || {
    echo "ERROR: Failed to fetch board data from ${API_URL}"
    exit 1
}

# Extract only the fields we need (compact JSON)
STATUS_JSON=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
out = {
    'timestamp': data['timestamp'],
    'totals': data['totals'],
    'summary': data['summary'],
}
print(json.dumps(out, separators=(',', ':')))
" <<< "${RAW}") || {
    echo "ERROR: Failed to parse API response"
    exit 1
}

cd "${REPO_DIR}"

# Ensure we're on the right branch
git checkout -B "${BRANCH}" 2>/dev/null || git checkout "${BRANCH}" 2>/dev/null

# Write the status file
mkdir -p data
echo "${STATUS_JSON}" > data/vlab_status.json

# Commit and push
git add data/vlab_status.json
if git diff --cached --quiet; then
    echo "No changes to commit"
else
    git commit -m "Update VLAB status $(date '+%Y-%m-%d %H:%M')"
    git -c core.sshCommand="${GIT_SSH}" push -f origin "${BRANCH}"
    echo "Pushed status update"
fi
