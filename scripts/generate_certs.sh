#!/usr/bin/env bash
# ============================================================================
# PANDA.1 v0.2.11 - HTTPS Certificate Generator
# ============================================================================
# Generates self-signed certificates for HTTPS mode.
# Required when accessing GUI from LAN IP (microphone permissions).
#
# Usage: ./generate_certs.sh
# ============================================================================

set -e

CERT_DIR="${HOME}/.panda1/certs"
CERT_FILE="${CERT_DIR}/panda.crt"
KEY_FILE="${CERT_DIR}/panda.key"
DAYS_VALID=365

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "=============================================="
echo "  PANDA.1 HTTPS Certificate Generator"
echo "=============================================="
echo ""

# Create cert directory
mkdir -p "${CERT_DIR}"
chmod 700 "${CERT_DIR}"

# Check if certs already exist
if [[ -f "${CERT_FILE}" && -f "${KEY_FILE}" ]]; then
    echo -e "${YELLOW}⚠ Certificates already exist:${NC}"
    echo "   ${CERT_FILE}"
    echo "   ${KEY_FILE}"
    echo ""
    read -p "Regenerate certificates? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing certificates."
        exit 0
    fi
fi

# Get local IP
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "192.168.1.17")

echo "Generating self-signed certificate..."
echo "  IP: ${LOCAL_IP}"
echo "  Valid: ${DAYS_VALID} days"
echo ""

# Generate certificate with SAN for localhost and local IP
openssl req -x509 -nodes -days ${DAYS_VALID} \
    -newkey rsa:2048 \
    -keyout "${KEY_FILE}" \
    -out "${CERT_FILE}" \
    -subj "/CN=PANDA.1/O=Local/C=US" \
    -addext "subjectAltName=DNS:localhost,DNS:panda1,IP:127.0.0.1,IP:${LOCAL_IP}"

# Set permissions
chmod 600 "${KEY_FILE}"
chmod 644 "${CERT_FILE}"

echo -e "${GREEN}✅ Certificates generated successfully!${NC}"
echo ""
echo "Files:"
echo "  Certificate: ${CERT_FILE}"
echo "  Private Key: ${KEY_FILE}"
echo ""
echo "To enable HTTPS, add to ~/.panda1/.env:"
echo "  PANDA_ENABLE_HTTPS=true"
echo "  PANDA_HTTPS_PORT=7860"
echo ""
echo "Then access GUI at:"
echo "  https://127.0.0.1:7860"
echo "  https://${LOCAL_IP}:7860"
echo ""
echo -e "${YELLOW}Note: Browser will show security warning for self-signed cert.${NC}"
echo "      Click 'Advanced' → 'Proceed' to accept."
echo ""
