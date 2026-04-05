#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
WEB_DIST_DIR="${ROOT_DIR}/web/dist"

mkdir -p "${ROOT_DIR}/runtime"

rm -f "${ROOT_DIR}/runtime/web.pid"

if [[ ! -f "${WEB_DIST_DIR}/index.html" ]]; then
  echo "Frontend build output not found, building web/dist"
  npm --prefix "${ROOT_DIR}/web" install
  npm --prefix "${ROOT_DIR}/web" run build
fi

echo "Starting web server in foreground on http://127.0.0.1:8000"
echo "Press Ctrl+C to stop."

exec env PYTHONPATH="${ROOT_DIR}/src" PYTHONUNBUFFERED=1 "${PYTHON_BIN}" -m doubao_automation.cli web
