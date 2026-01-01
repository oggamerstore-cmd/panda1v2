# PANDA.1 Networking Guide

## Overview

This guide explains how to configure PANDA.1's Ollama backend for network access, enabling integration with other agents like SENSEI and SCOTT.

### Network Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                         BOS Home Network                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐     ┌─────────────────┐     ┌──────────────┐  │
│  │   PANDA.1       │     │     SCOTT       │     │    SENSEI    │  │
│  │  192.168.1.17   │     │  192.168.1.18   │     │ 192.168.1.19 │  │
│  │                 │     │                 │     │              │  │
│  │  Ollama:11434   │◄────┤  FastAPI:8000   │     │  AgentHub    │  │
│  │  (LLM server)   │     │  (news agent)   │     │  (planned)   │  │
│  └────────▲────────┘     └─────────────────┘     └──────┬───────┘  │
│           │                                              │          │
│           └──────────────────────────────────────────────┘          │
│                    AgentHub connects to Ollama                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Reference

| Machine   | IP            | Port  | Service              |
|-----------|---------------|-------|----------------------|
| PANDA.1   | 192.168.1.17  | 11434 | Ollama (LLM)         |
| SCOTT     | 192.168.1.18  | 8000  | News Agent API       |
| SENSEI    | 192.168.1.19  | 8002  | Agent Hub (planned)  |

---

## Configuring Ollama for LAN Access

By default, Ollama only listens on `127.0.0.1:11434` (localhost). To allow other machines on your network to access it, you need to bind Ollama to `0.0.0.0:11434`.

### Step 1: Edit the Ollama systemd service

```bash
# On PANDA.1 machine (bos@PANDA)
sudo systemctl edit ollama --force
```

Add these lines (or edit `/etc/systemd/system/ollama.service` directly):

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

**Complete service file example** (`/etc/systemd/system/ollama.service`):

```ini
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/usr/local/bin/ollama serve
User=bos
Group=bos
Restart=always
RestartSec=3
Environment="OLLAMA_HOST=0.0.0.0:11434"

[Install]
WantedBy=default.target
```

### Step 2: Reload and restart Ollama

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### Step 3: Verify Ollama is listening on all interfaces

```bash
# Check listening ports
ss -lntp | grep 11434

# Expected output:
# LISTEN  0  4096  *:11434  *:*  users:(("ollama",pid=XXXX,fd=3))
```

The `*:11434` means Ollama is now listening on ALL interfaces (0.0.0.0).

### Step 4: Test connectivity

**Local test (on PANDA.1):**
```bash
curl http://localhost:11434/api/tags
```

**Remote test (from SENSEI or any other machine):**
```bash
curl http://192.168.1.17:11434/api/tags
```

Both should return a JSON list of available models.

---

## PANDA.1 CLI Health Check

PANDA.1 includes a built-in health check command:

```bash
# Quick check
panda --check-ollama

# Or the full health status
panda --status
```

**Example output:**

```
═══════════════════════════════════════════════════
  PANDA.1 Ollama Health Check
═══════════════════════════════════════════════════

✓ Connected to Ollama at http://localhost:11434

Models Available:
  • panda1:latest ✓ (primary)
  • qwen2.5:7b-instruct-q4_K_M ✓ (fallback)

Status: HEALTHY

═══════════════════════════════════════════════════
```

---

## Integration with SENSEI AgentHub

SENSEI's AgentHub connects to PANDA.1's Ollama directly. PANDA.1 does **not** need its own HTTP API for this - AgentHub talks to Ollama's `/api/chat` and `/api/tags` endpoints.

### SENSEI Configuration

In SENSEI's `agent_hub.py`:

```python
# PANDA.1 agent configuration
self.agents["panda1"] = AgentConfig(
    name="panda1",
    base_url="http://192.168.1.17:11434",  # ← Full URL with port!
    model="panda1:latest",
    health_endpoint="/api/tags"
)
```

**Common mistakes to avoid:**

| Wrong                              | Correct                               |
|------------------------------------|---------------------------------------|
| `http://localhost:11434`           | `http://192.168.1.17:11434`           |
| `http://192.168.1.17` (no port)    | `http://192.168.1.17:11434`           |
| `192.168.1.17:11434` (no scheme)   | `http://192.168.1.17:11434`           |

### Verifying AgentHub Connection

From SENSEI:

```bash
# Test health check (what AgentHub does internally)
curl http://192.168.1.17:11434/api/tags

# Test chat endpoint
curl -X POST http://192.168.1.17:11434/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "panda1:latest",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

---

## Integration with SCOTT

SCOTT is a separate news agent running on 192.168.1.18:8000. PANDA.1 connects to it as a client.

### PANDA.1 Configuration

In your `.env` file or environment:

```bash
PANDA_SCOTT_ENABLED=true
PANDA_SCOTT_API_URL=http://192.168.1.18:8000/api
PANDA_SCOTT_TIMEOUT=10
```

### Testing SCOTT Connection

From PANDA.1:

```bash
# Test SCOTT health
curl http://192.168.1.18:8000/api/health

# Test SCOTT news endpoint
curl http://192.168.1.18:8000/api/articles/top?limit=5
```

---

## Firewall Configuration (if needed)

If you have UFW or another firewall enabled, allow the necessary ports:

```bash
# On PANDA.1 - allow Ollama port
sudo ufw allow from 192.168.1.0/24 to any port 11434

# On SCOTT - allow API port
sudo ufw allow from 192.168.1.0/24 to any port 8000

# On SENSEI - allow AgentHub port (future)
sudo ufw allow from 192.168.1.0/24 to any port 8002
```

This only allows connections from your local network (192.168.1.0/24).

---

## Troubleshooting

### Problem: "Connection refused" from remote machine

**Cause:** Ollama is only listening on localhost (127.0.0.1)

**Solution:**
```bash
# Check current binding
ss -lntp | grep 11434

# If it shows 127.0.0.1:11434, fix the service file:
sudo nano /etc/systemd/system/ollama.service
# Add: Environment="OLLAMA_HOST=0.0.0.0:11434"

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### Problem: "Cannot connect to host ... port 80"

**Cause:** Missing port number in URL

**Solution:** Always include `:11434` in the URL:
```
✗ http://192.168.1.17         → Defaults to port 80
✓ http://192.168.1.17:11434   → Correct
```

### Problem: Model not found

**Cause:** Model not pulled or wrong model name

**Solution:**
```bash
# List available models
ollama list

# Pull the missing model
ollama pull qwen2.5:7b-instruct-q4_K_M

# Create panda1 model (if needed)
ollama create panda1 -f /path/to/modelfiles/PANDA1.modelfile
```

### Problem: Timeouts on first request

**Cause:** Model loading into VRAM takes time

**Solution:** Increase timeout or pre-warm the model:
```bash
# Pre-warm by sending a simple request
curl -X POST http://localhost:11434/api/generate \
  -d '{"model":"panda1:latest","prompt":"hi","stream":false}'
```

---

## Security Notes

⚠️ **LAN-only access:** The configuration in this guide allows ANY device on your local network (192.168.1.0/24) to access Ollama. This is intentional for PANDA.1's use case but be aware of the implications.

**Do NOT:**
- Expose port 11434 to the internet (don't port-forward it)
- Use this configuration on public networks

**Recommended:**
- Keep this on your private home network only
- Use firewall rules to restrict to specific IPs if needed
