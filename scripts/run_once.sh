#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

PYTHONPATH="${ROOT_DIR}/src" "${PYTHON_BIN}" -m doubao_automation.cli once
