#!/usr/bin/env bash
# Upload data/out/data.json to the Render service as the secret file data.json, then redeploy.
# Reads RENDER_API_KEY and RENDER_SERVICE_ID from ~/.env.
set -euo pipefail
set -a; source "$HOME/.env"; set +a
cd "$(dirname "$0")/.."
python3 -c 'import json,sys; print(json.dumps({"content": open("data/out/data.json").read()}))' > /tmp/wl-secret.json
curl -sf -X PUT "https://api.render.com/v1/services/$RENDER_SERVICE_ID/secret-files/data.json" \
  -H "Authorization: Bearer $RENDER_API_KEY" -H "Content-Type: application/json" -d @/tmp/wl-secret.json > /dev/null
rm -f /tmp/wl-secret.json
curl -sf -X POST "https://api.render.com/v1/services/$RENDER_SERVICE_ID/deploys" \
  -H "Authorization: Bearer $RENDER_API_KEY" -H "Content-Type: application/json" -d '{}' > /dev/null
echo "Data uploaded; redeploy started."
