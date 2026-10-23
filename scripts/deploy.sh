#!/usr/bin/env bash
# Copy app code to the public deploy repo, push it, and trigger a Render deploy.
# (Render has no GitHub link to the public repo, so pushes alone don't deploy.)
set -euo pipefail
set -a; source "$HOME/.env"; set +a
cd "$(dirname "$0")/.."
APP="$HOME/Projects/gio-work-log-app"
cp server.js package.json render.yaml README.md "$APP/"
cp public/index.html "$APP/public/"
cp scripts/build_data.py scripts/push_data.sh scripts/deploy.sh "$APP/scripts/"
git -C "$APP" add -A
git -C "$APP" diff --cached --quiet || git -C "$APP" commit -qm "${1:-Update app}"
git -C "$APP" push -q
curl -sf -X POST "https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys" \
  -H "Authorization: Bearer $RENDER_API_KEY" -H "Content-Type: application/json" -d '{}' > /dev/null
echo "Pushed and deploy started."
