"""
PANDA.1 Web GUI Server
======================
FastAPI-based web GUI for PANDA.1.

Version: 0.2.11

Features:
- Web-based GUI served locally or on LAN
- WebSocket for real-time chat with message_id correlation
- Log History panel for action tracking
- Sleep/wake screensaver mode
- Voice status indicators
- Always-on voice wake ("Hey Panda") integration
- Headless/SSH detection (server-only mode)
- Works with pandagui launcher for fullscreen kiosk mode

v0.2.10 Changes:
- HTTPS support for microphone access on LAN (192.168.1.17:7861)
- Auto TTS for all PANDA.1 messages (reads only PANDA responses)
- Dual language TTS: English (default) / Korean with voice commands
- Browser-based STT using MediaRecorder API + Faster-Whisper
- "panda speak korean" / "panda speak english" commands
- Push-to-talk (Space bar or mic icon) with browser audio capture
- Fixed STT to work properly with HTTPS

v0.2.10 Changes:
- Push-to-talk voice (Space bar or mic icon)
- Faster-Whisper STT (not openai-whisper)
- Kokoro TTS with real-time streaming
- Korean language support
- Fixed double bubble bug
- SCOTT LAN integration
- Desktop shortcut support
- Fixed Action Log 422 bug (ActionLogCreate model)
- Fixed streaming chat UI bubble bug (message_id correlation)
- Fixed WebSocket crash on language toggle (set_mode alias)
- Added GUI voice integration with "Hey Panda" wake
- Added thread-safe WebSocket broadcasting
- Added SCOTT offline handling
- Fixed version consistency
"""

import os
import sys
import json
import asyncio
import logging
import threading
import time
import uuid
import base64
import ssl
import socket
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from collections import deque

logger = logging.getLogger(__name__)

# Add app directory to path
APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    logger.error("FastAPI not installed. Install: pip install fastapi uvicorn")


# Version
__version__ = "0.2.11"


# Import TTS manager for voice functionality
try:
    from app.panda_tts import get_tts_manager, stop_speech
except ImportError:
    get_tts_manager = None
    stop_speech = None
    logger.warning("TTS manager not available")


# Action log storage (last 200 entries)
action_log: deque = deque(maxlen=200)
action_log_lock = threading.Lock()


class ActionLogEntry(BaseModel):
    """Action log entry model (stored entry with server-generated timestamp)."""
    timestamp: str
    action: str
    details: Optional[str] = None
    success: bool = True


class ActionLogCreate(BaseModel):
    """Action log create model (POST request - no timestamp required)."""
    action: str
    details: Optional[str] = None
    success: bool = True


def add_action_log(action: str, details: str = None, success: bool = True):
    """Add an entry to the action log."""
    with action_log_lock:
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "details": details,
            "success": success
        }
        action_log.append(entry)
        logger.debug(f"Action logged: {action}")


def get_action_logs() -> List[Dict]:
    """Get all action log entries."""
    with action_log_lock:
        return list(action_log)


def is_headless() -> bool:
    """Check if running in headless/SSH mode."""
    # Check for SSH connection
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        return True
    
    # Check for DISPLAY
    display = os.environ.get("DISPLAY")
    if not display:
        return True
    
    return False


def get_free_port(start_port: int = 7860, max_tries: int = 100) -> int:
    """Find a free port starting from start_port."""
    import socket
    for port in range(start_port, start_port + max_tries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No free port found in range {start_port}-{start_port + max_tries}")


def save_port_file(port: int, host: str) -> None:
    """Save the active port to a file."""
    from config import get_config
    config = get_config()
    port_file = config.gui_port_file
    port_file.parent.mkdir(parents=True, exist_ok=True)
    with open(port_file, 'w') as f:
        json.dump({"port": port, "host": host, "pid": os.getpid()}, f)


def load_port_file() -> Optional[Dict[str, Any]]:
    """Load the port file if it exists."""
    config = get_config()
    port_file = config.gui_port_file
    if port_file.exists():
        try:
            with open(port_file, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return None


# HTML template for the GUI with Log History panel and voice integration
GUI_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PANDA.1 - BOS Personal Edition</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a2e 50%, #0f0f23 100%);
            color: #e0e0e0;
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        .container {
            display: flex;
            flex-direction: column;
            height: 100vh;
            padding: 20px;
            gap: 15px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 20px;
            background: rgba(26, 26, 46, 0.8);
            border-radius: 10px;
            border: 1px solid #16213e;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: bold;
            color: #00d4ff;
        }
        
        .status-bar {
            display: flex;
            gap: 20px;
            font-size: 0.9rem;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #00ff88;
        }
        
        .status-dot.error { background: #ff4444; }
        .status-dot.warning { background: #ffaa00; }
        .status-dot.sleeping { background: #666; animation: pulse 2s infinite; }
        .status-dot.speaking { background: #00d4ff; animation: pulse 0.5s infinite; }
        .status-dot.listening { background: #00ff88; animation: pulse 0.8s infinite; }
        .status-dot.unavailable { background: #666; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .main-content {
            display: flex;
            flex: 1;
            gap: 20px;
            min-height: 0;
        }
        
        .chat-section {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 15px;
            min-width: 0;
        }
        
        .orb-section {
            width: 200px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 20px;
        }
        
        .orb-container {
            width: 150px;
            height: 150px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .orb {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: radial-gradient(circle at 30% 30%, 
                rgba(0, 212, 255, 0.8) 0%,
                rgba(0, 150, 200, 0.5) 40%,
                rgba(0, 100, 150, 0.3) 100%);
            box-shadow: 
                0 0 60px rgba(0, 212, 255, 0.4),
                inset 0 0 30px rgba(255, 255, 255, 0.1);
            animation: orbPulse 3s ease-in-out infinite;
        }
        
        .orb.sleeping {
            background: radial-gradient(circle at 30% 30%, 
                rgba(100, 100, 120, 0.6) 0%,
                rgba(60, 60, 80, 0.4) 40%,
                rgba(30, 30, 50, 0.3) 100%);
            box-shadow: 0 0 30px rgba(100, 100, 120, 0.2);
            animation: sleepPulse 4s ease-in-out infinite;
        }
        
        .orb.speaking {
            animation: speakPulse 0.3s ease-in-out infinite;
            box-shadow: 0 0 80px rgba(0, 212, 255, 0.6);
        }
        
        .orb.listening {
            background: radial-gradient(circle at 30% 30%, 
                rgba(0, 255, 136, 0.8) 0%,
                rgba(0, 200, 100, 0.5) 40%,
                rgba(0, 150, 75, 0.3) 100%);
            box-shadow: 0 0 60px rgba(0, 255, 136, 0.4);
            animation: listenPulse 0.8s ease-in-out infinite;
        }
        
        @keyframes orbPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        
        @keyframes sleepPulse {
            0%, 100% { opacity: 0.5; }
            50% { opacity: 0.8; }
        }
        
        @keyframes speakPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }
        
        @keyframes listenPulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 60px rgba(0, 255, 136, 0.4); }
            50% { transform: scale(1.08); box-shadow: 0 0 80px rgba(0, 255, 136, 0.6); }
        }
        
        .status-text {
            font-size: 1.1rem;
            color: #00d4ff;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        
        .chat-box {
            flex: 1;
            background: rgba(26, 26, 46, 0.6);
            border: 1px solid #16213e;
            border-radius: 10px;
            padding: 15px;
            overflow-y: auto;
        }
        
        .message {
            margin-bottom: 15px;
            padding: 10px 15px;
            border-radius: 8px;
            max-width: 85%;
        }
        
        .message.user {
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid rgba(0, 255, 136, 0.3);
            margin-left: auto;
        }
        
        .message.assistant {
            background: rgba(0, 212, 255, 0.1);
            border: 1px solid rgba(0, 212, 255, 0.3);
        }
        
        .message.system {
            background: rgba(136, 136, 136, 0.1);
            border: 1px solid rgba(136, 136, 136, 0.3);
            font-size: 0.9rem;
            text-align: center;
            margin: 10px auto;
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            font-size: 0.8rem;
            opacity: 0.7;
        }
        
        .message-sender {
            font-weight: bold;
        }
        
        .message-sender.user { color: #00ff88; }
        .message-sender.assistant { color: #00d4ff; }
        
        .message-content {
            line-height: 1.5;
            white-space: pre-wrap;
        }
        
        .input-section {
            display: flex;
            gap: 10px;
        }
        
        .input-field {
            flex: 1;
            padding: 15px;
            background: rgba(26, 26, 46, 0.8);
            border: 1px solid #16213e;
            border-radius: 10px;
            color: #e0e0e0;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.3s;
        }
        
        .input-field:focus {
            border-color: #00d4ff;
        }
        
        .send-btn {
            padding: 15px 30px;
            background: linear-gradient(135deg, #00d4ff, #0088aa);
            border: none;
            border-radius: 10px;
            color: white;
            font-size: 1rem;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .send-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }
        
        .send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .mic-btn {
            width: 50px;
            height: 50px;
            border-radius: 50%;
            background: linear-gradient(135deg, #00d4ff, #0088aa);
            border: none;
            color: white;
            font-size: 1.3rem;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .mic-btn:hover {
            transform: scale(1.1);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }

        .mic-btn.recording {
            background: linear-gradient(135deg, #ff4444, #cc0000);
            animation: micPulse 0.5s ease-in-out infinite;
        }

        .mic-btn.processing {
            background: linear-gradient(135deg, #ffaa00, #cc8800);
            animation: none;
        }

        @keyframes micPulse {
            0%, 100% { transform: scale(1); box-shadow: 0 0 20px rgba(255, 68, 68, 0.4); }
            50% { transform: scale(1.1); box-shadow: 0 0 40px rgba(255, 68, 68, 0.6); }
        }

        .transcript-box {
            padding: 15px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid #16213e;
            border-radius: 10px;
            font-size: 0.9rem;
            color: #888;
            min-height: 60px;
        }
        
        .transcript-label {
            font-size: 0.75rem;
            color: #666;
            margin-bottom: 5px;
        }
        
        .controls {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .control-btn {
            padding: 8px 16px;
            background: rgba(26, 26, 46, 0.8);
            border: 1px solid #16213e;
            border-radius: 5px;
            color: #888;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .control-btn:hover {
            background: rgba(0, 212, 255, 0.1);
            border-color: #00d4ff;
            color: #00d4ff;
        }
        
        .control-btn.active {
            background: rgba(0, 212, 255, 0.2);
            border-color: #00d4ff;
            color: #00d4ff;
        }
        
        /* Sleep overlay */
        .sleep-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.5s;
        }
        
        .sleep-overlay.active {
            opacity: 1;
            pointer-events: all;
        }
        
        .sleep-orb {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background: radial-gradient(circle at 30% 30%, 
                rgba(80, 80, 100, 0.6) 0%,
                rgba(50, 50, 70, 0.4) 40%,
                rgba(30, 30, 50, 0.2) 100%);
            animation: sleepBreath 4s ease-in-out infinite;
        }
        
        @keyframes sleepBreath {
            0%, 100% { transform: scale(0.95); opacity: 0.5; }
            50% { transform: scale(1.05); opacity: 0.8; }
        }
        
        .sleep-text {
            margin-top: 30px;
            font-size: 1.2rem;
            color: #666;
            animation: fadeText 3s ease-in-out infinite;
        }
        
        @keyframes fadeText {
            0%, 100% { opacity: 0.3; }
            50% { opacity: 0.7; }
        }
        
        .wake-hint {
            margin-top: 15px;
            font-size: 0.9rem;
            color: #444;
        }
        
        /* Log History Panel */
        .log-panel {
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 320px;
            max-height: 250px;
            background: rgba(26, 26, 46, 0.95);
            border: 1px solid #16213e;
            border-radius: 10px;
            z-index: 100;
            display: flex;
            flex-direction: column;
        }
        
        .log-panel-header {
            padding: 10px 15px;
            border-bottom: 1px solid #16213e;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .log-panel-title {
            font-size: 0.85rem;
            color: #888;
            font-weight: bold;
        }
        
        .log-panel-toggle {
            background: none;
            border: none;
            color: #666;
            cursor: pointer;
            font-size: 0.8rem;
        }
        
        .log-panel-content {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
            max-height: 180px;
        }
        
        .log-entry {
            font-size: 0.75rem;
            padding: 4px 8px;
            margin-bottom: 4px;
            border-radius: 4px;
            background: rgba(0, 0, 0, 0.2);
        }
        
        .log-entry.success {
            border-left: 2px solid #00ff88;
        }
        
        .log-entry.error {
            border-left: 2px solid #ff4444;
        }
        
        .log-time {
            color: #666;
            margin-right: 8px;
        }
        
        .log-action {
            color: #00d4ff;
        }
        
        .log-details {
            color: #888;
            font-size: 0.7rem;
        }
        
        /* Toast notifications */
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: rgba(26, 26, 46, 0.95);
            border: 1px solid #16213e;
            border-radius: 8px;
            z-index: 2000;
            transform: translateX(400px);
            transition: transform 0.3s ease;
        }
        
        .toast.show {
            transform: translateX(0);
        }
        
        .toast.success {
            border-color: #00ff88;
        }
        
        .toast.error {
            border-color: #ff4444;
        }
        
        /* SCOTT offline warning */
        .warning-banner {
            background: rgba(255, 170, 0, 0.1);
            border: 1px solid rgba(255, 170, 0, 0.3);
            border-radius: 5px;
            padding: 8px 15px;
            font-size: 0.85rem;
            color: #ffaa00;
            display: none;
        }
        
        .warning-banner.visible {
            display: block;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🐼 PANDA.1 <span style="font-size: 0.7em; color: #666;">v0.2.11</span></div>
            <div class="status-bar">
                <div class="status-item">
                    <span class="status-dot" id="llmStatus"></span>
                    <span id="llmLabel">LLM</span>
                </div>
                <div class="status-item">
                    <span class="status-dot sleeping" id="micStatus"></span>
                    <span id="micLabel">SLEEPING</span>
                </div>
                <div class="status-item">
                    <span class="status-dot" id="ttsStatus"></span>
                    <span id="ttsLabel">TTS</span>
                </div>
                <div class="status-item">
                    <span class="status-dot" id="scottStatus"></span>
                    <span id="scottLabel">SCOTT</span>
                </div>
                <div class="status-item">
                    <span class="status-dot" id="langStatus"></span>
                    <span id="langLabel">EN</span>
                </div>
            </div>
        </div>
        
        <div class="warning-banner" id="scottWarning">
            ⚠️ SCOTT news agent is offline. News features may be limited.
        </div>
        
        <div class="main-content">
            <div class="chat-section">
                <div class="chat-box" id="chatBox">
                    <div class="message assistant" data-message-id="init">
                        <div class="message-header">
                            <span class="message-sender assistant">PANDA.1</span>
                            <span class="message-time"></span>
                        </div>
                        <div class="message-content">Hello BOS! I'm ready to assist you. Hold the mic button or press Space to speak. Say "panda speak korean" or "panda speak english" to switch languages.</div>
                    </div>
                </div>
                
                <div class="transcript-box">
                    <div class="transcript-label">Live Transcript</div>
                    <div id="transcript">Waiting for voice input...</div>
                </div>
                
                <div class="input-section">
                    <button class="mic-btn" id="micBtn" title="Hold to speak (or press Space)">🎤</button>
                    <input type="text" class="input-field" id="messageInput"
                           placeholder="Type or hold mic/Space to speak... (say 'panda speak korean' to switch)"
                           autocomplete="off">
                    <button class="send-btn" id="sendBtn">Send</button>
                </div>

                <div class="controls">
                    <button class="control-btn" id="langToggle">🌐 EN/KO</button>
                    <button class="control-btn" id="wakeBtn">📢 Wake</button>
                    <button class="control-btn" id="sleepBtn">💤 Sleep</button>
                    <button class="control-btn" id="clearBtn">🗑️ Clear</button>
                    <button class="control-btn" id="statusBtn">📊 Status</button>
                    <button class="control-btn" id="stopTtsBtn">🔇 Stop TTS</button>
                    <button class="control-btn" id="testTtsBtn">🔊 Test TTS</button>
                </div>
            </div>
            
            <div class="orb-section">
                <div class="orb-container">
                    <div class="orb" id="orb"></div>
                </div>
                <div class="status-text" id="orbStatus">READY</div>
            </div>
        </div>
    </div>
    
    <div class="sleep-overlay" id="sleepOverlay">
        <div class="sleep-orb"></div>
        <div class="sleep-text">😴 PANDA.1 is sleeping...</div>
        <div class="wake-hint">Say "Hey Panda" or click anywhere to wake</div>
    </div>
    
    <!-- Log History Panel -->
    <div class="log-panel" id="logPanel">
        <div class="log-panel-header">
            <span class="log-panel-title">📋 Log History</span>
            <button class="log-panel-toggle" id="logToggle">−</button>
        </div>
        <div class="log-panel-content" id="logContent">
            <div class="log-entry success">
                <span class="log-time">--:--</span>
                <span class="log-action">GUI Started</span>
            </div>
        </div>
    </div>
    
    <!-- Toast container -->
    <div class="toast" id="toast"></div>
    
    <script>
        const chatBox = document.getElementById('chatBox');
        const messageInput = document.getElementById('messageInput');
        const sendBtn = document.getElementById('sendBtn');
        const orb = document.getElementById('orb');
        const orbStatus = document.getElementById('orbStatus');
        const sleepOverlay = document.getElementById('sleepOverlay');
        const transcript = document.getElementById('transcript');
        const logContent = document.getElementById('logContent');
        const toast = document.getElementById('toast');
        const scottWarning = document.getElementById('scottWarning');
        
        let ws = null;
        let isSleeping = false;
        let lastActivity = Date.now();
        const SLEEP_TIMEOUT = 5 * 60 * 1000; // 5 minutes
        let logPanelCollapsed = false;
        let currentMessageId = null;  // Track current streaming message
        let messageElements = {};  // Map message_id to DOM element
        
        // Show toast notification
        function showToast(message, type = 'success') {
            toast.textContent = message;
            toast.className = 'toast ' + type + ' show';
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
        
        // Generate unique message ID
        function generateMessageId() {
            return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        }
        
        // Add to action log (server-side)
        async function logAction(action, details = null, success = true) {
            try {
                await fetch('/api/ui/action-log', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action, details, success})
                });
            } catch (e) {
                console.error('Failed to log action:', e);
            }
        }
        
        // Update log panel
        async function updateLogPanel() {
            try {
                const res = await fetch('/api/ui/action-log');
                const logs = await res.json();
                
                logContent.innerHTML = logs.slice(-20).reverse().map(log => `
                    <div class="log-entry ${log.success ? 'success' : 'error'}">
                        <span class="log-time">${log.timestamp}</span>
                        <span class="log-action">${log.action}</span>
                        ${log.details ? `<div class="log-details">${log.details}</div>` : ''}
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to update log panel:', e);
            }
        }
        
        // API call wrapper with error handling
        async function apiCall(endpoint, method = 'POST', body = null) {
            try {
                const options = {
                    method,
                    headers: {'Content-Type': 'application/json'}
                };
                if (body) options.body = JSON.stringify(body);
                
                const res = await fetch(endpoint, options);
                const data = await res.json();
                
                if (!data.ok) {
                    showToast(data.message || 'Action failed', 'error');
                    return null;
                }
                return data;
            } catch (e) {
                showToast('Network error: ' + e.message, 'error');
                return null;
            }
        }
        
        function connect() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                updateStatus('llmStatus', true);
                logAction('WebSocket Connected');
            };
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleMessage(data);
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                updateStatus('llmStatus', false);
                setTimeout(connect, 3000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        }
        
        function handleMessage(data) {
            switch(data.type) {
                case 'response':
                    addMessage('assistant', data.content, data.message_id);
                    setProcessing(false);
                    break;
                case 'stream':
                    // Append to message with matching message_id
                    appendToMessage(data.content, data.message_id);
                    break;
                case 'stream_start':
                    // Create placeholder for new assistant message
                    createAssistantPlaceholder(data.message_id);
                    break;
                case 'stream_end':
                    setProcessing(false);
                    currentMessageId = null;
                    break;
                case 'status':
                    updateStatusBar(data);
                    break;
                case 'speaking':
                    setSpeaking(data.speaking);
                    break;
                case 'wake':
                    wake();
                    updateMicStatus('LISTENING');
                    break;
                case 'voice_state':
                    updateMicStatus(data.state);
                    break;
                case 'transcript':
                    transcript.textContent = data.content || 'Waiting for voice input...';
                    break;
                case 'voice_command':
                    // Voice command received - add as user message
                    addMessage('user', data.transcript, data.message_id);
                    setProcessing(true);
                    break;
                case 'scott_status':
                    updateScottStatus(data.online);
                    break;
                case 'error':
                    addMessage('system', 'Error: ' + data.content);
                    showToast(data.content, 'error');
                    setProcessing(false);
                    break;
            }
        }
        
        function sendMessage() {
            const message = messageInput.value.trim();
            if (!message || !ws) return;
            
            wake();
            const messageId = generateMessageId();
            addMessage('user', message, messageId);
            messageInput.value = '';
            setProcessing(true);
            logAction('Chat Message Sent', message.substring(0, 50));
            
            // Create placeholder for assistant response
            createAssistantPlaceholder(messageId + '_response');
            currentMessageId = messageId + '_response';
            
            ws.send(JSON.stringify({
                type: 'chat',
                content: message,
                message_id: messageId
            }));
        }
        
        function addMessage(type, content, messageId = null) {
            const time = new Date().toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'});
            const sender = type === 'user' ? 'BOS' : type === 'assistant' ? 'PANDA.1' : 'System';
            const id = messageId || generateMessageId();
            
            const div = document.createElement('div');
            div.className = 'message ' + type;
            div.setAttribute('data-message-id', id);
            div.innerHTML = `
                <div class="message-header">
                    <span class="message-sender ${type}">${sender}</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-content">${escapeHtml(content)}</div>
            `;
            
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
            messageElements[id] = div;
            resetActivityTimer();
        }
        
        function createAssistantPlaceholder(messageId) {
            const time = new Date().toLocaleTimeString('en-US', {hour: '2-digit', minute: '2-digit'});
            
            const div = document.createElement('div');
            div.className = 'message assistant';
            div.setAttribute('data-message-id', messageId);
            div.innerHTML = `
                <div class="message-header">
                    <span class="message-sender assistant">PANDA.1</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-content"></div>
            `;
            
            chatBox.appendChild(div);
            chatBox.scrollTop = chatBox.scrollHeight;
            messageElements[messageId] = div;
            currentMessageId = messageId;
        }
        
        function appendToMessage(content, messageId) {
            // Use provided message_id or fall back to current
            const targetId = messageId || currentMessageId;
            let targetElement = null;
            
            if (targetId && messageElements[targetId]) {
                targetElement = messageElements[targetId];
            } else {
                // Fallback: append to last assistant message
                const messages = chatBox.querySelectorAll('.message.assistant');
                if (messages.length > 0) {
                    targetElement = messages[messages.length - 1];
                }
            }
            
            if (targetElement) {
                const contentDiv = targetElement.querySelector('.message-content');
                contentDiv.textContent += content;
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function setProcessing(processing) {
            sendBtn.disabled = processing;
            orbStatus.textContent = processing ? 'PROCESSING' : 'READY';
            if (processing) {
                orb.style.animation = 'orbPulse 0.5s ease-in-out infinite';
            } else {
                orb.style.animation = '';
            }
        }
        
        function setSpeaking(speaking) {
            if (speaking) {
                orb.classList.add('speaking');
                orb.classList.remove('listening', 'sleeping');
                orbStatus.textContent = 'SPEAKING';
                updateStatus('ttsStatus', true);
            } else {
                orb.classList.remove('speaking');
                orbStatus.textContent = 'READY';
            }
        }
        
        function updateMicStatus(state) {
            const micDot = document.getElementById('micStatus');
            const micLabel = document.getElementById('micLabel');
            
            micLabel.textContent = state;
            micDot.className = 'status-dot';
            
            switch(state) {
                case 'SLEEPING':
                    micDot.classList.add('sleeping');
                    orb.classList.add('sleeping');
                    orb.classList.remove('listening', 'speaking');
                    break;
                case 'LISTENING':
                case 'AWAKE_LISTENING':
                    micDot.classList.add('listening');
                    orb.classList.add('listening');
                    orb.classList.remove('sleeping', 'speaking');
                    break;
                case 'PROCESSING':
                    micDot.classList.remove('sleeping', 'listening');
                    break;
                case 'UNAVAILABLE':
                    micDot.classList.add('unavailable');
                    micLabel.textContent = 'MIC N/A';
                    break;
                default:
                    break;
            }
        }
        
        function updateStatus(elementId, isOk) {
            const dot = document.getElementById(elementId);
            if (dot) {
                dot.className = 'status-dot' + (isOk ? '' : ' error');
            }
        }
        
        function updateScottStatus(online) {
            updateStatus('scottStatus', online);
            document.getElementById('scottLabel').textContent = online ? 'SCOTT' : 'SCOTT ❌';
            scottWarning.classList.toggle('visible', !online);
        }
        
        function updateStatusBar(data) {
            if (data.llm) updateStatus('llmStatus', data.llm.healthy);
            if (data.tts) updateStatus('ttsStatus', data.tts.available);
            if (data.language) document.getElementById('langLabel').textContent = data.language.toUpperCase();
            if (data.mic) {
                updateMicStatus(data.mic);
            }
            if (data.scott !== undefined) {
                updateScottStatus(data.scott);
            }
        }
        
        function wake() {
            isSleeping = false;
            sleepOverlay.classList.remove('active');
            orb.classList.remove('sleeping');
            resetActivityTimer();
            
            // Notify server
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'voice_wake'}));
            }
        }
        
        function sleep() {
            isSleeping = true;
            sleepOverlay.classList.add('active');
            orb.classList.add('sleeping');
            orb.classList.remove('listening', 'speaking');
            document.getElementById('micLabel').textContent = 'SLEEPING';
            
            // Notify server
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'voice_sleep'}));
            }
        }
        
        function resetActivityTimer() {
            lastActivity = Date.now();
        }
        
        function checkSleepTimer() {
            if (!isSleeping && Date.now() - lastActivity > SLEEP_TIMEOUT) {
                sleep();
            }
        }
        
        // Button event listeners with action logging
        sendBtn.addEventListener('click', sendMessage);
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
            resetActivityTimer();
        });
        
        sleepOverlay.addEventListener('click', () => {
            wake();
            logAction('Wake (click overlay)');
        });
        
        document.getElementById('wakeBtn').addEventListener('click', async () => {
            wake();
            logAction('Wake Button');
            showToast('PANDA.1 is awake!', 'success');
        });
        
        document.getElementById('sleepBtn').addEventListener('click', async () => {
            sleep();
            logAction('Sleep Button');
        });
        
        document.getElementById('clearBtn').addEventListener('click', async () => {
            chatBox.innerHTML = '';
            messageElements = {};
            addMessage('system', 'Chat cleared');
            logAction('Clear Chat');
            showToast('Chat cleared', 'success');
        });
        
        document.getElementById('langToggle').addEventListener('click', async () => {
            logAction('Toggle Language');
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'toggle_language'}));
            }
        });
        
        document.getElementById('statusBtn').addEventListener('click', async () => {
            logAction('Status Check');
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'get_status'}));
            }
        });
        
        document.getElementById('stopTtsBtn').addEventListener('click', async () => {
            logAction('Stop TTS');
            const result = await apiCall('/api/tts/stop');
            if (result) {
                showToast('TTS stopped', 'success');
                setSpeaking(false);
            }
        });
        
        document.getElementById('testTtsBtn').addEventListener('click', async () => {
            logAction('Test TTS');
            const result = await apiCall('/api/tts/test');
            if (result) {
                showToast('TTS test: ' + result.message, result.ok ? 'success' : 'error');
            }
        });
        
        // Log panel toggle
        document.getElementById('logToggle').addEventListener('click', () => {
            logPanelCollapsed = !logPanelCollapsed;
            logContent.style.display = logPanelCollapsed ? 'none' : 'block';
            document.getElementById('logToggle').textContent = logPanelCollapsed ? '+' : '−';
        });

        // =========================================================================
        // Push-to-Talk with MediaRecorder API (v0.2.10)
        // =========================================================================
        const micBtn = document.getElementById('micBtn');
        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let recordingStartTime = null;
        let currentTtsLanguage = 'en';

        // Check for microphone permission
        async function checkMicPermission() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                stream.getTracks().forEach(track => track.stop());
                return true;
            } catch (e) {
                console.error('Microphone access denied:', e);
                return false;
            }
        }

        // Start recording
        async function startRecording() {
            if (isRecording) return;

            try {
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000,
                        echoCancellation: true,
                        noiseSuppression: true,
                    }
                });

                // Use audio/webm for MediaRecorder (will be converted server-side)
                const mimeType = MediaRecorder.isTypeSupported('audio/webm')
                    ? 'audio/webm'
                    : 'audio/mp4';

                mediaRecorder = new MediaRecorder(stream, { mimeType });
                audioChunks = [];

                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };

                mediaRecorder.onstop = async () => {
                    // Stop all tracks
                    stream.getTracks().forEach(track => track.stop());

                    // Process audio
                    await processRecording();
                };

                mediaRecorder.start();
                isRecording = true;
                recordingStartTime = Date.now();

                // Update UI
                micBtn.classList.add('recording');
                micBtn.textContent = '🔴';
                transcript.textContent = 'Recording... (release to send)';
                orb.classList.add('listening');
                orbStatus.textContent = 'LISTENING';

                logAction('Recording Started');

            } catch (e) {
                console.error('Failed to start recording:', e);
                showToast('Microphone access denied. HTTPS required for mic access.', 'error');
                transcript.textContent = 'Mic access denied. Use HTTPS for voice input.';
            }
        }

        // Stop recording
        function stopRecording() {
            if (!isRecording || !mediaRecorder) return;

            const recordingDuration = Date.now() - recordingStartTime;

            // Minimum recording duration (300ms)
            if (recordingDuration < 300) {
                mediaRecorder.stop();
                isRecording = false;
                micBtn.classList.remove('recording');
                micBtn.textContent = '🎤';
                transcript.textContent = 'Recording too short. Hold longer to speak.';
                return;
            }

            mediaRecorder.stop();
            isRecording = false;

            // Update UI
            micBtn.classList.remove('recording');
            micBtn.classList.add('processing');
            micBtn.textContent = '⏳';
            transcript.textContent = 'Processing speech...';
            orb.classList.remove('listening');
            orbStatus.textContent = 'PROCESSING';
        }

        // Process recorded audio
        async function processRecording() {
            if (audioChunks.length === 0) {
                micBtn.classList.remove('processing');
                micBtn.textContent = '🎤';
                transcript.textContent = 'No audio recorded';
                return;
            }

            try {
                // Create blob from chunks
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

                // Convert to base64
                const reader = new FileReader();
                reader.onloadend = async () => {
                    const base64Audio = reader.result.split(',')[1];

                    // Send to server for transcription
                    try {
                        const response = await fetch('/api/stt/transcribe', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ audio: base64Audio })
                        });

                        const data = await response.json();

                        if (data.ok && data.text) {
                            // Got transcription - send as message
                            transcript.textContent = data.text;
                            logAction('STT Success', data.text.substring(0, 50));

                            // Send the transcribed text as a chat message
                            wake();
                            const messageId = generateMessageId();
                            addMessage('user', data.text, messageId);
                            setProcessing(true);

                            createAssistantPlaceholder(messageId + '_response');
                            currentMessageId = messageId + '_response';

                            if (ws && ws.readyState === WebSocket.OPEN) {
                                ws.send(JSON.stringify({
                                    type: 'chat',
                                    content: data.text,
                                    message_id: messageId
                                }));
                            }
                        } else {
                            transcript.textContent = data.message || 'No speech detected. Try again.';
                            showToast('No speech detected', 'error');
                        }
                    } catch (e) {
                        console.error('Transcription error:', e);
                        transcript.textContent = 'Transcription failed: ' + e.message;
                        showToast('Transcription failed', 'error');
                    }

                    // Reset UI
                    micBtn.classList.remove('processing');
                    micBtn.textContent = '🎤';
                    orbStatus.textContent = 'READY';
                };

                reader.readAsDataURL(audioBlob);

            } catch (e) {
                console.error('Audio processing error:', e);
                micBtn.classList.remove('processing');
                micBtn.textContent = '🎤';
                transcript.textContent = 'Audio processing failed';
            }
        }

        // Mic button mouse/touch events (push-to-talk)
        micBtn.addEventListener('mousedown', (e) => {
            e.preventDefault();
            startRecording();
        });

        micBtn.addEventListener('mouseup', (e) => {
            e.preventDefault();
            stopRecording();
        });

        micBtn.addEventListener('mouseleave', () => {
            if (isRecording) stopRecording();
        });

        // Touch events for mobile
        micBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            startRecording();
        });

        micBtn.addEventListener('touchend', (e) => {
            e.preventDefault();
            stopRecording();
        });

        // Space bar push-to-talk (when not typing)
        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space' && document.activeElement !== messageInput && !isRecording) {
                e.preventDefault();
                startRecording();
            }
        });

        document.addEventListener('keyup', (e) => {
            if (e.code === 'Space' && isRecording) {
                e.preventDefault();
                stopRecording();
            }
        });

        // Handle TTS language updates from server
        function updateTtsLanguage(lang) {
            currentTtsLanguage = lang;
            const langLabel = document.getElementById('langLabel');
            if (langLabel) {
                langLabel.textContent = lang.toUpperCase();
            }
        }

        // Update handleMessage to handle tts_language
        const originalHandleMessage = handleMessage;
        handleMessage = function(data) {
            // Handle TTS language in status updates
            if (data.type === 'status' && data.tts_language) {
                updateTtsLanguage(data.tts_language);
            }
            originalHandleMessage(data);
        };

        // Check mic permission on load
        checkMicPermission().then(hasPermission => {
            if (!hasPermission) {
                transcript.textContent = 'Mic access needed. Click mic button to allow.';
            }
        });

        // Initialize
        connect();
        setInterval(checkSleepTimer, 10000);
        setInterval(updateLogPanel, 5000);
        updateLogPanel();
    </script>
</body>
</html>
'''


if FASTAPI_AVAILABLE:
    
    app = FastAPI(title="PANDA.1 GUI", version=__version__)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Global state
    panda_core = None
    active_connections: List[WebSocket] = []
    connections_lock = threading.Lock()
    voice_state = {"mic": "SLEEPING", "transcript": "", "speaking": False}
    scott_status = {"online": None, "last_check": 0}

    # TTS state (v0.2.11)
    tts_language = "en"  # Current TTS language: "en" or "ko"
    tts_auto_enabled = True  # Auto TTS for PANDA.1 messages
    kokoro_tts = None  # Kokoro TTS instance

    # STT state (v0.2.11 - singleton pattern for performance)
    faster_whisper_stt = None  # Global STT instance to avoid model reload overhead
    
    # Thread-safe broadcast queue for WebSocket events
    broadcast_queue: asyncio.Queue = None
    main_loop: asyncio.AbstractEventLoop = None
    
    # Voice assistant instance (for GUI integration)
    voice_assistant = None
    voice_thread = None
    
    
    def get_panda():
        """Get or create PandaCore instance."""
        global panda_core
        if panda_core is None:
            from panda_core import PandaCore
            panda_core = PandaCore()
        return panda_core
    
    
    async def broadcast_to_clients(message: dict):
        """Broadcast message to all connected WebSocket clients."""
        with connections_lock:
            dead_connections = []
            for ws in active_connections:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.debug(f"Failed to send to client: {e}")
                    dead_connections.append(ws)
            
            # Remove dead connections
            for ws in dead_connections:
                if ws in active_connections:
                    active_connections.remove(ws)
    
    
    def queue_broadcast(message: dict):
        """
        Thread-safe function to queue a broadcast message.
        Can be called from any thread.
        """
        global broadcast_queue, main_loop
        if broadcast_queue is not None and main_loop is not None:
            try:
                main_loop.call_soon_threadsafe(
                    lambda: broadcast_queue.put_nowait(message)
                )
            except Exception as e:
                logger.error(f"Failed to queue broadcast: {e}")
    
    
    async def broadcast_worker():
        """Async worker that processes the broadcast queue."""
        global broadcast_queue
        broadcast_queue = asyncio.Queue()
        
        while True:
            try:
                message = await broadcast_queue.get()
                await broadcast_to_clients(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Broadcast worker error: {e}")
    
    
    def check_scott_status():
        """Check SCOTT status with rate limiting."""
        global scott_status
        
        # Rate limit: check at most every 60 seconds
        now = time.time()
        if now - scott_status["last_check"] < 60:
            return scott_status["online"]
        
        scott_status["last_check"] = now
        
        try:
            config = get_config()
            
            if not config.scott_enabled:
                scott_status["online"] = None
                return None
            
            import requests
            response = requests.get(
                f"{config.scott_api_url}/health",
                timeout=3
            )
            scott_status["online"] = response.status_code == 200
        except Exception:
            scott_status["online"] = False
        
        return scott_status["online"]


    def init_kokoro_tts():
        """Initialize Kokoro TTS engine."""
        global kokoro_tts

        if kokoro_tts is not None:
            return kokoro_tts

        try:
            from app.voice.tts_kokoro import KokoroTTS, KOKORO_AVAILABLE

            if not KOKORO_AVAILABLE:
                logger.warning("Kokoro TTS not available")
                return None

            config = get_config()

            kokoro_tts = KokoroTTS(
                voice_en="am_michael",  # American Male Michael
                voice_ko="km_omega",    # Korean Male Omega
                speed=config.tts_speed,
                device=config.tts_device,
            )

            # Initialize both language pipelines
            if kokoro_tts.initialize("both"):
                logger.info("Kokoro TTS initialized for auto TTS")
                return kokoro_tts
            else:
                logger.warning("Failed to initialize Kokoro TTS")
                return None

        except Exception as e:
            logger.error(f"Failed to init Kokoro TTS: {e}")
            return None


    def speak_panda_response(text: str, lang: str = None):
        """
        Speak PANDA.1's response using Kokoro TTS.

        Args:
            text: Text to speak
            lang: Language (en/ko), defaults to current tts_language
        """
        global tts_language, kokoro_tts

        if not text or not text.strip():
            return

        use_lang = lang or tts_language

        try:
            # Initialize TTS if needed
            if kokoro_tts is None:
                kokoro_tts = init_kokoro_tts()

            if kokoro_tts is None:
                logger.warning("TTS not available, skipping speech")
                return

            # Signal speaking start
            queue_broadcast({"type": "speaking", "speaking": True})

            # Synthesize and play
            result = kokoro_tts.synthesize(text, use_lang)

            if result.success and result.audio_data:
                # Play with sounddevice
                try:
                    import sounddevice as sd
                    import numpy as np
                    import wave
                    import io

                    wav_io = io.BytesIO(result.audio_data)
                    with wave.open(wav_io, 'rb') as wav:
                        frames = wav.readframes(wav.getnframes())
                        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767

                    sd.play(audio, result.sample_rate)
                    sd.wait()

                except Exception as e:
                    logger.warning(f"Playback failed: {e}")
                    # Fallback to panda_tts
                    try:
                        from app.panda_tts import get_tts_manager
                        manager = get_tts_manager()
                        if manager.is_ready:
                            manager.speak(text, use_lang, blocking=True)
                    except Exception as e:
                        logging.error(f'Exception caught: {e}')
                        pass

            # Signal speaking end
            queue_broadcast({"type": "speaking", "speaking": False})

        except Exception as e:
            logger.error(f"TTS error: {e}")
            queue_broadcast({"type": "speaking", "speaking": False})


    def process_language_switch(text: str) -> tuple:
        """
        Check if text contains language switch command.

        Returns:
            (is_switch_command, new_language, acknowledgment)
        """
        global tts_language

        text_lower = text.lower().strip()

        # Check for "panda speak korean" variations
        korean_patterns = [
            "panda speak korean",
            "panda, speak korean",
            "speak korean",
            "switch to korean",
            "korean mode",
            "한국어로 말해",
            "판다 한국어",
        ]

        # Check for "panda speak english" variations
        english_patterns = [
            "panda speak english",
            "panda, speak english",
            "speak english",
            "switch to english",
            "english mode",
            "영어로 말해",
            "판다 영어",
        ]

        for pattern in korean_patterns:
            if pattern in text_lower:
                old_lang = tts_language
                tts_language = "ko"
                ack = "네, 알겠습니다. 이제 한국어로 말할게요." if old_lang != "ko" else "이미 한국어 모드입니다."
                logger.info(f"TTS language switched to Korean")
                return True, "ko", ack

        for pattern in english_patterns:
            if pattern in text_lower:
                old_lang = tts_language
                tts_language = "en"
                ack = "Okay, I'll speak in English now." if old_lang != "en" else "I'm already in English mode."
                logger.info(f"TTS language switched to English")
                return True, "en", ack

        return False, None, None


    def get_stt_instance():
        """
        Get or create the global STT instance (singleton pattern).

        This avoids the 2-5s model loading overhead on each transcription.
        """
        global faster_whisper_stt

        if faster_whisper_stt is None:
            try:
                from app.voice.stt_faster_whisper import FasterWhisperSTT
                config = get_config()

                faster_whisper_stt = FasterWhisperSTT(
                    model_size=config.stt_model,
                    device=config.stt_device,
                    compute_type=config.stt_compute_type,
                )

                # Pre-load the model
                if faster_whisper_stt.load_model():
                    logger.info(f"STT model loaded: {config.stt_model}")
                else:
                    logger.warning("Failed to pre-load STT model")

            except Exception as e:
                logger.error(f"Failed to initialize STT: {e}")
                return None

        return faster_whisper_stt


    def transcribe_audio(audio_data: bytes) -> str:
        """
        Transcribe audio using Faster-Whisper.

        Args:
            audio_data: Audio bytes (webm or WAV format)

        Returns:
            Transcribed text
        """
        try:
            import tempfile
            import subprocess

            # Save audio to temp file
            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
                f.write(audio_data)
                input_path = f.name

            # Convert webm to wav using ffmpeg
            output_path = input_path.replace('.webm', '.wav')

            try:
                result = subprocess.run([
                    'ffmpeg', '-y', '-i', input_path,
                    '-ar', '16000', '-ac', '1', '-f', 'wav',
                    output_path
                ], capture_output=True, timeout=30)

                if result.returncode != 0:
                    logger.warning(f"ffmpeg conversion failed: {result.stderr.decode()}")
                    # Try using the input directly
                    output_path = input_path

            except FileNotFoundError:
                logger.warning("ffmpeg not found, trying direct transcription")
                output_path = input_path
            except Exception as e:
                logger.warning(f"Audio conversion error: {e}")
                output_path = input_path

            # Get global STT instance (avoids model reload overhead)
            stt = get_stt_instance()

            if stt is None:
                logger.error("STT instance not available")
                return ""

            # Read the audio file
            with open(output_path, 'rb') as f:
                wav_data = f.read()

            # Transcribe
            result = stt.transcribe(wav_data)

            # Cleanup temp files
            try:
                Path(input_path).unlink(missing_ok=True)
                if output_path != input_path:
                    Path(output_path).unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"Temp file cleanup error: {e}")

            if result and hasattr(result, 'text') and result.text:
                return result.text.strip()
            elif result and isinstance(result, dict) and result.get("text"):
                return result["text"].strip()

            return ""

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""


    def start_voice_assistant():
        """Start the voice assistant for GUI mode."""
        global voice_assistant, voice_thread, voice_state
        
        config = get_config()
        
        if not config.gui_voice_enabled:
            logger.info("GUI voice disabled by config")
            voice_state["mic"] = "DISABLED"
            return False
        
        try:
            from voice_assistant import VoiceAssistant, VoiceState
            
            def on_wake():
                """Called when wake phrase detected."""
                logger.info("Wake detected in GUI mode")
                voice_state["mic"] = "AWAKE_LISTENING"
                queue_broadcast({"type": "wake"})
                queue_broadcast({"type": "voice_state", "state": "AWAKE_LISTENING"})
                
                # Optional TTS acknowledgment
                if config.voice_ack_enabled:
                    try:
                        manager = get_tts_manager()
                        if manager.is_ready:
                            queue_broadcast({"type": "speaking", "speaking": True})
                            
                            def speak_ack():
                                manager.speak("Yes BOS.", blocking=True)
                                queue_broadcast({"type": "speaking", "speaking": False})
                            
                            threading.Thread(target=speak_ack, daemon=True).start()
                    except Exception as e:
                        logger.debug(f"TTS ack error: {e}")
            
            def on_command(text: str):
                """Called when command received via voice."""
                logger.info(f"Voice command: {text}")
                voice_state["mic"] = "PROCESSING"
                voice_state["transcript"] = text
                
                # Generate message ID for this voice command
                message_id = f"voice_{int(time.time() * 1000)}"
                
                # Broadcast user message (voice transcript)
                queue_broadcast({
                    "type": "voice_command",
                    "transcript": text,
                    "message_id": message_id
                })
                
                # Process and stream response
                def process_voice_command():
                    try:
                        panda = get_panda()
                        response_id = message_id + "_response"
                        
                        # Signal stream start
                        queue_broadcast({
                            "type": "stream_start",
                            "message_id": response_id
                        })
                        
                        full_response = ""
                        for chunk in panda.process_stream(text):
                            full_response += chunk
                            queue_broadcast({
                                "type": "stream",
                                "content": chunk,
                                "message_id": response_id
                            })
                        
                        queue_broadcast({
                            "type": "stream_end",
                            "message_id": response_id
                        })
                        
                        # Speak response via TTS
                        try:
                            manager = get_tts_manager()
                            if manager.is_ready and full_response:
                                queue_broadcast({"type": "speaking", "speaking": True})
                                manager.speak(full_response, blocking=True)
                                queue_broadcast({"type": "speaking", "speaking": False})
                        except Exception as e:
                            logger.debug(f"TTS error: {e}")
                        
                        voice_state["mic"] = "AWAKE_LISTENING"
                        queue_broadcast({"type": "voice_state", "state": "AWAKE_LISTENING"})
                        
                    except Exception as e:
                        logger.error(f"Voice command processing error: {e}")
                        queue_broadcast({"type": "error", "content": str(e)})
                
                threading.Thread(target=process_voice_command, daemon=True).start()
            
            def on_state_change(state: VoiceState):
                """Called when voice state changes."""
                voice_state["mic"] = state.name
                queue_broadcast({"type": "voice_state", "state": state.name})
            
            def on_transcript(text: str):
                """Called for live transcript updates."""
                voice_state["transcript"] = text
                queue_broadcast({"type": "transcript", "content": text})
            
            voice_assistant = VoiceAssistant(
                wake_phrases=config.wake_phrase_list,
                sleep_timeout=config.sleep_timeout_minutes * 60,
                audio_input_device=config.audio_input_device,
                on_wake=on_wake,
                on_command=on_command,
                on_state_change=on_state_change,
                on_transcript=on_transcript,
            )
            
            if voice_assistant.start():
                logger.info("Voice assistant started for GUI mode")
                voice_state["mic"] = "SLEEPING"
                return True
            else:
                logger.warning("Voice assistant failed to start - mic may be unavailable")
                voice_state["mic"] = "UNAVAILABLE"
                return False
                
        except ImportError as e:
            logger.warning(f"Voice assistant not available: {e}")
            voice_state["mic"] = "UNAVAILABLE"
            return False
        except Exception as e:
            logger.error(f"Failed to start voice assistant: {e}")
            voice_state["mic"] = "UNAVAILABLE"
            return False
    
    
    def stop_voice_assistant():
        """Stop the voice assistant."""
        global voice_assistant
        if voice_assistant:
            voice_assistant.stop()
            voice_assistant = None
    
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize on server startup."""
        global main_loop, broadcast_queue
        
        main_loop = asyncio.get_event_loop()
        
        # Start broadcast worker
        asyncio.create_task(broadcast_worker())
        
        # Start voice assistant in background thread
        threading.Thread(target=start_voice_assistant, daemon=True).start()
        
        # Initial SCOTT check
        threading.Thread(target=check_scott_status, daemon=True).start()
        
        add_action_log("GUI Server Started", f"v{__version__}")
    
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on server shutdown."""
        stop_voice_assistant()
    
    
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main GUI page."""
        return HTMLResponse(content=GUI_HTML)
    
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"ok": True, "status": "healthy", "version": __version__}
    
    
    @app.get("/api/status")
    async def api_status():
        """Get system status."""
        panda = get_panda()
        status = panda.get_status()
        status["scott_online"] = check_scott_status()
        return {"ok": True, "data": status}
    
    
    # =========================================================================
    # Action Log API (FIXED in v0.2.10)
    # =========================================================================
    
    @app.get("/api/ui/action-log")
    async def get_action_log():
        """Get action log entries."""
        return get_action_logs()
    
    
    @app.post("/api/ui/action-log")
    async def post_action_log(entry: ActionLogCreate):
        """
        Add action log entry.
        
        NOTE: Uses ActionLogCreate which does NOT require timestamp.
        Timestamp is generated server-side.
        """
        add_action_log(entry.action, entry.details, entry.success)
        return {"ok": True, "message": "Logged"}
    
    
    # =========================================================================
    # Voice Control API
    # =========================================================================
    
    @app.get("/api/voice/status")
    async def voice_status():
        """Get voice assistant status."""
        global voice_assistant, voice_state
        
        status = {
            "enabled": voice_assistant is not None,
            "state": voice_state.get("mic", "UNAVAILABLE"),
            "transcript": voice_state.get("transcript", ""),
        }
        
        if voice_assistant:
            status.update(voice_assistant.get_status())
        
        return {"ok": True, "data": status}
    
    
    @app.post("/api/voice/wake")
    async def voice_wake():
        """Manually wake the voice assistant."""
        global voice_assistant
        
        if voice_assistant:
            voice_assistant.wake()
            return {"ok": True, "message": "Voice assistant woken"}
        return {"ok": False, "message": "Voice assistant not available"}
    
    
    @app.post("/api/voice/sleep")
    async def voice_sleep():
        """Manually put voice assistant to sleep."""
        global voice_assistant
        
        if voice_assistant:
            voice_assistant.sleep()
            return {"ok": True, "message": "Voice assistant sleeping"}
        return {"ok": False, "message": "Voice assistant not available"}
    
    
    # =========================================================================
    # TTS API
    # =========================================================================
    
    @app.post("/api/tts/stop")
    async def tts_stop():
        """Stop TTS playback."""
        try:
            from app.panda_tts import stop_speech
            stop_speech()
            add_action_log("TTS Stopped", None, True)
            await broadcast_to_clients({"type": "speaking", "speaking": False})
            return {"ok": True, "message": "TTS stopped"}
        except Exception as e:
            add_action_log("TTS Stop Failed", str(e), False)
            return {"ok": False, "message": str(e)}
    
    
    @app.post("/api/tts/test")
    async def tts_test():
        """Test TTS with a short phrase."""
        try:
            
            manager = get_tts_manager()
            if not manager.is_ready:
                manager.initialize()
            
            health = manager.healthcheck()
            if not health.get("healthy"):
                add_action_log("TTS Test Failed", health.get("error"), False)
                return {"ok": False, "message": f"TTS unhealthy: {health.get('error')}"}
            
            # Synthesize test phrase
            audio_path = manager.synthesize("Hello, this is PANDA speaking.")
            if audio_path:
                await broadcast_to_clients({"type": "speaking", "speaking": True})
                
                def play_test():
                    manager.speak("Hello, this is PANDA speaking.", blocking=True)
                    queue_broadcast({"type": "speaking", "speaking": False})
                
                threading.Thread(target=play_test, daemon=True).start()
                
                add_action_log("TTS Test", f"Engine: {health.get('engine')}", True)
                return {"ok": True, "message": f"Playing via {health.get('engine')}"}
            else:
                add_action_log("TTS Test Failed", "Synthesis failed", False)
                return {"ok": False, "message": "Synthesis failed"}
                
        except Exception as e:
            add_action_log("TTS Test Error", str(e), False)
            return {"ok": False, "message": str(e)}
    
    
    @app.get("/api/tts/status")
    async def tts_status():
        """Get TTS status."""
        try:
            manager = get_tts_manager()
            health = manager.healthcheck()
            return {"ok": True, "data": health}
        except Exception as e:
            return {"ok": False, "message": str(e)}


    @app.get("/api/tts/language")
    async def tts_get_language():
        """Get current TTS language."""
        return {"ok": True, "language": tts_language}


    @app.post("/api/tts/language")
    async def tts_set_language(request: Request):
        """Set TTS language."""
        global tts_language
        try:
            data = await request.json()
            lang = data.get("language", "en").lower()
            if lang in ("en", "ko"):
                tts_language = lang
                add_action_log("TTS Language", f"Set to {lang.upper()}", True)
                return {"ok": True, "language": tts_language}
            return {"ok": False, "message": "Invalid language. Use 'en' or 'ko'"}
        except Exception as e:
            return {"ok": False, "message": str(e)}


    # =========================================================================
    # STT API (v0.2.10 - Browser-based audio transcription)
    # =========================================================================

    @app.post("/api/stt/transcribe")
    async def stt_transcribe(request: Request):
        """
        Transcribe audio from browser MediaRecorder.

        Expects base64-encoded WAV audio in request body.
        """
        try:
            data = await request.json()
            audio_base64 = data.get("audio", "")

            if not audio_base64:
                return {"ok": False, "message": "No audio data provided"}

            # Decode base64 audio
            audio_data = base64.b64decode(audio_base64)

            # Transcribe using Faster-Whisper
            text = transcribe_audio(audio_data)

            if text:
                add_action_log("STT Transcription", text[:50], True)
                return {"ok": True, "text": text}
            else:
                return {"ok": False, "message": "No speech detected"}

        except Exception as e:
            logger.error(f"STT transcribe error: {e}")
            add_action_log("STT Error", str(e), False)
            return {"ok": False, "message": str(e)}


    @app.get("/api/stt/status")
    async def stt_status():
        """Get STT status."""
        try:
            from app.voice.stt_faster_whisper import FASTER_WHISPER_AVAILABLE
            return {
                "ok": True,
                "data": {
                    "available": FASTER_WHISPER_AVAILABLE,
                    "engine": "faster-whisper",
                }
            }
        except Exception as e:
            return {"ok": False, "message": str(e)}


    # =========================================================================
    # WebSocket (FIXED in v0.2.10, updated v0.2.10)
    # =========================================================================
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket endpoint for real-time chat."""
        await websocket.accept()
        
        with connections_lock:
            active_connections.append(websocket)
        
        panda = get_panda()
        
        try:
            # Send initial status
            status = panda.get_status()
            scott_online = check_scott_status()
            
            await websocket.send_json({
                "type": "status",
                "llm": status.get("llm", {}),
                "language": status.get("language", "en"),
                "mic": voice_state.get("mic", "SLEEPING"),
                "scott": scott_online
            })
            
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type", "")
                
                if msg_type == "chat":
                    content = data.get("content", "")
                    client_message_id = data.get("message_id", "")

                    if content:
                        # Check for language switch command first
                        is_lang_switch, new_lang, ack_msg = process_language_switch(content)

                        if is_lang_switch:
                            # Language switch command - respond with acknowledgment
                            response_id = client_message_id + "_response" if client_message_id else f"resp_{int(time.time() * 1000)}"

                            await websocket.send_json({
                                "type": "stream_start",
                                "message_id": response_id
                            })
                            await websocket.send_json({
                                "type": "stream",
                                "content": ack_msg,
                                "message_id": response_id
                            })
                            await websocket.send_json({
                                "type": "stream_end",
                                "message_id": response_id
                            })

                            # Broadcast language change
                            await websocket.send_json({
                                "type": "status",
                                "language": new_lang,
                                "tts_language": new_lang
                            })

                            # Speak acknowledgment in new language
                            def speak_ack():
                                speak_panda_response(ack_msg, new_lang)
                            threading.Thread(target=speak_ack, daemon=True).start()

                            continue  # Skip normal processing

                        # Generate response message ID
                        response_id = client_message_id + "_response" if client_message_id else f"resp_{int(time.time() * 1000)}"

                        # Process and stream response
                        try:
                            # Signal stream start with message_id
                            await websocket.send_json({
                                "type": "stream_start",
                                "message_id": response_id
                            })

                            full_response = ""
                            for chunk in panda.process_stream(content):
                                full_response += chunk
                                await websocket.send_json({
                                    "type": "stream",
                                    "content": chunk,
                                    "message_id": response_id
                                })

                            await websocket.send_json({
                                "type": "stream_end",
                                "message_id": response_id
                            })

                            # Auto TTS: Speak PANDA.1's response using Kokoro
                            if full_response and tts_auto_enabled:
                                def speak_response():
                                    speak_panda_response(full_response)
                                threading.Thread(target=speak_response, daemon=True).start()

                        except Exception as e:
                            await websocket.send_json({
                                "type": "error",
                                "content": str(e)
                            })
                
                elif msg_type == "toggle_language":
                    global tts_language
                    # Toggle TTS language
                    new_lang = "ko" if tts_language == "en" else "en"
                    tts_language = new_lang

                    # Also update language mode manager
                    from language_mode import get_language_manager
                    lang_mgr = get_language_manager()
                    lang_mgr.set_mode(new_lang)

                    msg = "Switched to Korean mode (한국어). 이제 한국어로 말할게요." if new_lang == "ko" else "Switched to English mode. I'll speak in English now."
                    await websocket.send_json({
                        "type": "response",
                        "content": msg
                    })
                    await websocket.send_json({
                        "type": "status",
                        "language": new_lang,
                        "tts_language": new_lang
                    })

                    # Speak the switch confirmation
                    def speak_switch():
                        speak_panda_response(msg, new_lang)
                    threading.Thread(target=speak_switch, daemon=True).start()
                
                elif msg_type == "voice_wake":
                    if voice_assistant:
                        voice_assistant.wake()
                
                elif msg_type == "voice_sleep":
                    if voice_assistant:
                        voice_assistant.sleep()
                
                elif msg_type == "get_status":
                    status = panda.get_status()
                    scott_online = check_scott_status()
                    
                    lines = [f"PANDA.1 v{__version__} Status:"]
                    
                    llm = status.get("llm", {})
                    lines.append(f"LLM: {'Connected' if llm.get('healthy') else 'Offline'}")
                    
                    if status.get("openai"):
                        openai_status = status["openai"]
                        lines.append(f"OpenAI: {'Available' if openai_status.get('available') else 'Not configured'}")
                    
                    # SCOTT status (non-blocking)
                    if scott_online is not None:
                        lines.append(f"SCOTT: {'Connected' if scott_online else 'Offline'}")
                    
                    if status.get("penny"):
                        penny = status["penny"]
                        lines.append(f"PENNY: {'Connected' if penny.get('healthy') else 'Offline'}")
                    
                    if status.get("memory"):
                        mem = status["memory"]
                        lines.append(f"Memory: {mem.get('count', 0)} items")
                    
                    # TTS status
                    try:
                        manager = get_tts_manager()
                        health = manager.healthcheck()
                        lines.append(f"TTS: {health.get('engine', 'unknown')} ({health.get('device', 'unknown')})")
                    except Exception as e:
                        logging.error(f'Exception caught: {e}')
                        lines.append("TTS: Not available")
                    
                    # Voice status
                    lines.append(f"Voice: {voice_state.get('mic', 'UNAVAILABLE')}")
                    lines.append(f"Language: {status.get('language', 'en').upper()}")
                    
                    await websocket.send_json({
                        "type": "response",
                        "content": "\n".join(lines)
                    })
                    
        except WebSocketDisconnect:
            with connections_lock:
                if websocket in active_connections:
                    active_connections.remove(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            with connections_lock:
                if websocket in active_connections:
                    active_connections.remove(websocket)


def run_server(host: Optional[str] = None, port: Optional[int] = None, use_https: bool = None) -> int:
    """
    Run the GUI server with optional HTTPS support.

    Args:
        host: Host to bind to (defaults to config)
        port: Port to use (defaults to config, auto-detect if busy)
        use_https: Enable HTTPS (defaults to config.enable_https)

    Returns:
        Exit code
    """
    if not FASTAPI_AVAILABLE:
        logging.error("Error: FastAPI not installed.")
        logging.info("Install: pip install fastapi uvicorn")
        return 1

    config = get_config()

    # Get host and port from config if not specified
    if host is None:
        host = config.gui_host
    if port is None:
        port = config.https_port if (use_https or config.enable_https) else config.gui_port
    if use_https is None:
        use_https = config.enable_https

    # Check if port is available, find another if not
    try:
        actual_port = get_free_port(port)
    except RuntimeError as e:
        logging.error(f"Error: {e}")
        return 1

    # Save port file
    save_port_file(actual_port, host)

    # HTTPS certificate setup
    ssl_certfile = None
    ssl_keyfile = None

    if use_https:
        cert_dir = config.certs_dir
        ssl_certfile = cert_dir / "panda.crt"
        ssl_keyfile = cert_dir / "panda.key"

        if not ssl_certfile.exists() or not ssl_keyfile.exists():
            logging.info()
            logging.info("=" * 60)
            logging.info("  ⚠️  HTTPS CERTIFICATES NOT FOUND")
            logging.info("=" * 60)
            logging.info()
            logging.info(f"  Expected locations:")
            logging.info(f"    Certificate: {ssl_certfile}")
            logging.info(f"    Private Key: {ssl_keyfile}")
            logging.info()
            logging.info("  Generate certificates with:")
            logging.info("    cd /home/user/panda1 && ./scripts/generate_certs.sh")
            logging.info()
            logging.info("  Or disable HTTPS:")
            logging.info("    PANDA_ENABLE_HTTPS=false")
            logging.info()
            return 1

    # Log startup info
    headless = is_headless()
    protocol = "https" if use_https else "http"

    logging.info()
    logging.info("=" * 60)
    logging.info(f"  PANDA.1 GUI Server v{__version__}")
    logging.info("=" * 60)
    logging.info()
    logging.info(f"  Host: {host}")
    logging.info(f"  Port: {actual_port}")
    logging.info(f"  Protocol: {protocol.upper()}")
    logging.info(f"  Mode: {'Headless (server-only)' if headless else 'Desktop'}")
    logging.info(f"  Voice: {'Enabled' if config.gui_voice_enabled else 'Disabled'}")
    logging.info(f"  TTS Language: EN (default), use 'panda speak korean' to switch")
    logging.info()

    if host == "0.0.0.0":
        # Get actual LAN IP, not loopback
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception as e:
            logging.error(f'Exception caught: {e}')
            local_ip = "192.168.1.17"  # Fallback to PANDA's known IP
        logging.info(f"  Local URL:   {protocol}://127.0.0.1:{actual_port}")
        logging.info(f"  LAN URL:     {protocol}://{local_ip}:{actual_port}")
        if use_https:
            logging.info()
            logging.warning("  ⚠️  Browser will show security warning for self-signed cert.")
            logging.info("     Click 'Advanced' → 'Proceed' to accept.")
    else:
        logging.info(f"  URL: {protocol}://{host}:{actual_port}")

    logging.info()
    logging.info("  Press Ctrl+C to stop")
    logging.info("=" * 60)
    logging.info()

    # Setup logging
    log_dir = config.logs_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pandagui.log"

    # Configure uvicorn logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["handlers"]["file"] = {
        "class": "logging.FileHandler",
        "filename": str(log_file),
        "formatter": "default"
    }
    log_config["loggers"]["uvicorn"]["handlers"].append("file")

    try:
        # Build uvicorn arguments
        uvicorn_kwargs = {
            "host": host,
            "port": actual_port,
            "log_level": "info",
            "access_log": True,
            "log_config": log_config,
        }

        # Add SSL if HTTPS enabled
        if use_https:
            uvicorn_kwargs["ssl_certfile"] = str(ssl_certfile)
            uvicorn_kwargs["ssl_keyfile"] = str(ssl_keyfile)

        uvicorn.run(app, **uvicorn_kwargs)
        return 0
    except KeyboardInterrupt:
        logging.info("\nShutting down...")
        return 0
    except Exception as e:
        logging.error(f"Server error: {e}")
        logger.exception("Server error")
        return 1


def get_server_url() -> Optional[str]:
    """Get the URL of the running server."""
    port_info = load_port_file()
    if port_info:
        host = port_info.get('host', '127.0.0.1')
        if host == '0.0.0.0':
            host = '127.0.0.1'
        return f"http://{host}:{port_info['port']}"
    return None


if __name__ == "__main__":
    run_server()
