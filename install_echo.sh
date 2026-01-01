#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ECHO_HOME="${ECHO_HOME:-$HOME/.echo}"
VENV_DIR="${ECHO_HOME}/venv"
ENV_FILE="${ECHO_HOME}/.env"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/echo.service"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🧠 ECHO Database PC Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required."
  exit 1
fi

mkdir -p "${ECHO_HOME}"

if [ ! -d "${VENV_DIR}" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "${VENV_DIR}"
fi

echo "Installing Python dependencies..."
"${VENV_DIR}/bin/pip" install --upgrade pip >/dev/null
"${VENV_DIR}/bin/pip" install fastapi uvicorn qdrant-client fastembed python-dotenv >/dev/null

if [ ! -f "${ENV_FILE}" ]; then
  cat <<EOF > "${ENV_FILE}"
ECHO_HOST=0.0.0.0
ECHO_PORT=9010
ECHO_COLLECTION=echo_vectors
ECHO_EMBED_MODEL=BAAI/bge-small-en-v1.5
# ECHO_QDRANT_URL=http://127.0.0.1:6333
# ECHO_QDRANT_API_KEY=
EOF
fi

mkdir -p "${SERVICE_DIR}"
cat <<EOF > "${SERVICE_FILE}"
[Unit]
Description=ECHO Vector Server
After=network.target

[Service]
Type=simple
WorkingDirectory=${SCRIPT_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python -m app.echo_server
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF

if command -v systemctl >/dev/null 2>&1; then
  systemctl --user daemon-reload
  systemctl --user enable --now echo.service || true
  echo ""
  echo "ECHO service installed."
  echo "Check status: systemctl --user status echo.service"
else
  echo ""
  echo "systemctl not available. Run manually:"
  echo "  ${VENV_DIR}/bin/python -m app.echo_server"
fi

echo ""
echo "ECHO configuration: ${ENV_FILE}"
echo "ECHO data directory: ${ECHO_HOME}"
