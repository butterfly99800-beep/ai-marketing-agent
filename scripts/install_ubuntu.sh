#!/usr/bin/env bash
# Run as ubuntu, not root, after installing OS prerequisites listed in DEPLOY_UBUNTU.md.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(id -u)" = 0 ]; then echo 'Run as ubuntu, not root.' >&2; exit 1; fi
node -e 'if(Number(process.versions.node.split(".")[0])<22)process.exit(1)'
python3.12 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r requirements.lock.txt
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
(cd renderer && npm ci --no-audit --no-fund && npx playwright install chromium)
mkdir -p work/projects work/secrets/youtube renderer/public/projects
chmod 700 work/secrets
.venv/bin/python scripts/check_deployment.py
printf '\nNext: copy .env.example to .env, fill keys, chmod 600 .env, create operator, configure systemd/nginx.\n'
