#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="${ROOT_DIR}/runtime/web.pid"

if [[ ! -f "${PID_FILE}" ]]; then
  echo "No background web server PID file found."
  echo "If the server is running in the current terminal, stop it with Ctrl+C."
  exit 0
fi

PID="$(cat "${PID_FILE}")"
if kill -0 "${PID}" 2>/dev/null; then
  kill "${PID}"
  echo "Sent SIGTERM to ${PID}."
else
  echo "PID ${PID} is not active."
fi

rm -f "${PID_FILE}"
