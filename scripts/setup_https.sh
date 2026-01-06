#!/bin/bash
# =============================================================================
# PANDA.1 HTTPS Setup Script
# =============================================================================
# Generates self-signed SSL certificate for HTTPS mode
# =============================================================================

PANDA_HOME="${HOME}/.panda1"
CERT_DIR="${PANDA_HOME}/certs"
CERT_FILE="${CERT_DIR}/cert.pem"
KEY_FILE="${CERT_DIR}/key.pem"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  🔒 PANDA.1 HTTPS Setup${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Create certs directory
mkdir -p "${CERT_DIR}"

# Check if certificates already exist
if [ -f "${CERT_FILE}" ] && [ -f "${KEY_FILE}" ]; then
    echo "Certificates already exist:"
    echo "  Cert: ${CERT_FILE}"
    echo "  Key:  ${KEY_FILE}"
    echo ""
    read -p "Regenerate? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing certificates."
        exit 0
    fi
fi

# Get hostname
HOSTNAME=$(hostname)
IP_ADDR=$(hostname -I | awk '{print $1}')

echo "Generating self-signed certificate..."
echo "  Hostname: ${HOSTNAME}"
echo "  IP Address: ${IP_ADDR}"
echo ""

# Generate certificate with SANs for localhost and LAN IP
openssl req -x509 -newkey rsa:4096 -keyout "${KEY_FILE}" -out "${CERT_FILE}" \
    -days 365 -nodes \
    -subj "/CN=${HOSTNAME}/O=PANDA.1/C=US" \
    -addext "subjectAltName=DNS:localhost,DNS:${HOSTNAME},IP:127.0.0.1,IP:${IP_ADDR}"

# Set permissions
chmod 600 "${KEY_FILE}"
chmod 644 "${CERT_FILE}"

echo ""
echo -e "${GREEN}✅ Certificate generated successfully!${NC}"
echo ""
echo "Certificate: ${CERT_FILE}"
echo "Private Key: ${KEY_FILE}"
echo "Valid for: 365 days"
echo ""
echo "To enable HTTPS, add to ~/.panda1/.env:"
echo ""
echo "  PANDA_ENABLE_HTTPS=1"
echo "  PANDA_HTTPS_PORT=7860"
echo ""
echo "Then start PANDA:"
echo "  panda --gui"
echo ""
echo "Access via:"
echo "  https://127.0.0.1:7860"
echo "  https://${IP_ADDR}:7860"
echo ""
echo -e "${YELLOW}Note: Browser will show security warning (self-signed cert).${NC}"
echo -e "${YELLOW}Click 'Advanced' → 'Proceed' to access.${NC}"
echo ""
