#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_ROOT="${ROOT_DIR}/release"
PACKAGE_NAME="doubao-mac-distribution"
STAGING_DIR="${RELEASE_ROOT}/${PACKAGE_NAME}"
ZIP_PATH="${RELEASE_ROOT}/${PACKAGE_NAME}.zip"
WEB_DIST_DIR="${ROOT_DIR}/web/dist"

echo "Preparing release package at ${RELEASE_ROOT}"
mkdir -p "${RELEASE_ROOT}"

if [[ ! -f "${ROOT_DIR}/.env" ]]; then
  echo "Missing ${ROOT_DIR}/.env"
  echo "Create it first, or copy .env.example to .env and fill in the values you want to ship."
  exit 1
fi

if [[ ! -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  echo "Missing ${ROOT_DIR}/.venv/bin/python"
  echo "Run ./scripts/bootstrap.sh first."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to rebuild the frontend before packaging."
  exit 1
fi

echo "Rebuilding frontend to ensure web/dist is up to date"
npm --prefix "${ROOT_DIR}/web" install
npm --prefix "${ROOT_DIR}/web" run build

if [[ ! -f "${WEB_DIST_DIR}/index.html" ]]; then
  echo "Frontend build failed: ${WEB_DIST_DIR}/index.html not found"
  exit 1
fi

echo "Refreshing staging directory"
rm -rf "${STAGING_DIR}" "${ZIP_PATH}"
mkdir -p "${STAGING_DIR}"

cp -R "${ROOT_DIR}/src" "${STAGING_DIR}/src"
cp -R "${ROOT_DIR}/scripts" "${STAGING_DIR}/scripts"
mkdir -p "${STAGING_DIR}/web"
cp -R "${WEB_DIST_DIR}" "${STAGING_DIR}/web/dist"
cp "${ROOT_DIR}/pyproject.toml" "${STAGING_DIR}/pyproject.toml"
cp "${ROOT_DIR}/README.md" "${STAGING_DIR}/README.md"
cp "${ROOT_DIR}/.env" "${STAGING_DIR}/.env"
cp "${ROOT_DIR}/.env.example" "${STAGING_DIR}/.env.example"

mkdir -p "${STAGING_DIR}/runtime"

echo "Creating zip archive"
(
  cd "${RELEASE_ROOT}"
  /usr/bin/zip -qry "${ZIP_PATH}" "${PACKAGE_NAME}"
)

echo "Package ready:"
echo "  Directory: ${STAGING_DIR}"
echo "  Archive:   ${ZIP_PATH}"
echo
echo "Recipient prerequisites:"
echo "  1. Install Python 3.12"
echo "  2. Install Google Chrome"
echo "  3. Run ./scripts/bootstrap.sh"
echo "  4. Run ./scripts/install_browser.sh"
echo "  5. Run ./scripts/start.sh"
