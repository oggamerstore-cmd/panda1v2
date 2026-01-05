#!/usr/bin/env python3
"""
PANDA.1 - Personal AI Navigator & Digital Assistant
===================================================
BOS Personal Edition

Version: 0.2.11

CLI Usage:
  panda                    Launch GUI (default)
  panda --gui              Launch GUI
  panda --cli              Interactive CLI mode
  panda --voice            Voice assistant mode (wake phrase: "Hey Panda")
  panda --api              Start API server
  panda --check-ollama     Ollama health check
  panda --status           Full system status
  panda --audio-devices    List audio INPUT and OUTPUT devices
  panda --mic-test         Test microphone input (records 3s, reports levels)
  panda --audio-test       Test audio playback
  panda --tts-test         Test TTS
  panda --gui-doctor       GUI-specific diagnostics
  panda --voice-doctor     Voice system diagnostics (v0.2.10)
  panda --doctor           TTS diagnostics
  panda -q "message"       Single query mode
  panda --help             Show all options

Agent Commands (v0.2.10):
  panda --scott-doctor     SCOTT news agent diagnostics
  panda --penny-doctor     PENNY finance agent diagnostics
  panda --sensei-doctor    SENSEI learning hub diagnostics
  panda --echo-doctor      ECHO context hub diagnostics
  panda --agents-doctor    Check all agents at once
  panda --news [topic]     Get news from SCOTT
  panda --penny "query"    Query PENNY for JNJ FOODS LLC finances
  panda --learn [topic]    Learn from SENSEI (download lessons to memory)
  panda --echo "query"     Query ECHO for context snippets

Interactive CLI Commands:
  /news [topic]            Get news from SCOTT
  /penny <query>           Query PENNY finance agent
  /sensei                  Show SENSEI status
  /learn [topic]           Learn from SENSEI
  /echo <query>            Query ECHO for context snippets

GUI is the PRIMARY interface. CLI is secondary.
"""

import sys
import os
import argparse
from typing import Optional

# Version info
__version__ = "0.2.11"
__author__ = "BOS"

# TTS state (can be toggled with /voice)
_voice_enabled = True


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='panda',
        description='PANDA.1 - Personal AI Navigator & Digital Assistant',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  panda                      Start GUI (default)
  panda --cli                Start interactive CLI
  panda --voice              Start voice assistant (say "Hey Panda" to wake)
  panda --check-ollama       Check Ollama connectivity
  panda --status             Show full system status
  panda --audio-devices      List all input/output audio devices
  panda --mic-test           Test microphone (records 3 seconds)
  panda --gui-doctor         Run GUI diagnostics
  panda -q "What's the weather?"  Single query
        """
    )
    
    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--gui', '-g',
        action='store_true',
        help='Launch GUI (this is the default if no mode specified)'
    )
    mode_group.add_argument(
        '--cli', '-c',
        action='store_true',
        help='Interactive CLI mode'
    )
    mode_group.add_argument(
        '--api', '-a',
        action='store_true',
        help='Start API server'
    )
    mode_group.add_argument(
        '--voice', '-v',
        action='store_true',
        help='Voice assistant mode with wake phrase detection'
    )
    
    # Query options
    parser.add_argument(
        '--query', '-q',
        nargs='+',
        metavar='MSG',
        help='Single query (non-interactive)'
    )
    
    # Health checks
    parser.add_argument(
        '--check-ollama',
        action='store_true',
        help='Check Ollama health and model availability'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show full system status'
    )
    
    # News commands
    parser.add_argument(
        '--news',
        nargs='?',
        const='top',
        metavar='TOPIC',
        help='Get news (optionally specify topic)'
    )
    
    # Server options
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=None,
        help='GUI/API server port (defaults to config values)'
    )
    
    # Behavior options
    parser.add_argument(
        '--no-stream',
        action='store_true',
        help='Disable streaming responses'
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug output'
    )
    
    # Language options
    parser.add_argument(
        '--language', '-l',
        choices=['en', 'ko'],
        default=None,
        help='Set output language mode (en=English, ko=Korean)'
    )
    
    # Info
    parser.add_argument(
        '--version', '-V',
        action='version',
        version=f'PANDA.1 v{__version__}'
    )
    parser.add_argument(
        '--config',
        action='store_true',
        help='Show current configuration'
    )
    
    # TTS tools
    parser.add_argument(
        '--doctor',
        action='store_true',
        help='Run TTS diagnostics and show fix steps'
    )
    parser.add_argument(
        '--tts-test',
        nargs='?',
        const='Hello, I am PANDA.1!',
        metavar='TEXT',
        help='Test TTS with optional text'
    )
    parser.add_argument(
        '--tts-prefetch',
        action='store_true',
        help='Download TTS models for offline use'
    )
    
    # Audio tools (enhanced in v0.2.10)
    parser.add_argument(
        '--audio-devices',
        action='store_true',
        help='List ALL audio devices (INPUT and OUTPUT with indices)'
    )
    parser.add_argument(
        '--audio-test',
        action='store_true',
        help='Test audio playback with a beep'
    )
    parser.add_argument(
        '--mic-test',
        nargs='?',
        const=3,
        type=int,
        metavar='SECONDS',
        help='Test microphone input (default: 3 seconds)'
    )
    
    # GUI diagnostics (new in v0.2.10)
    parser.add_argument(
        '--gui-doctor',
        action='store_true',
        help='Run GUI-specific diagnostics (WebSocket, voice, TTS, etc.)'
    )

    # Agent diagnostics (v0.2.10)
    parser.add_argument(
        '--scott-doctor',
        action='store_true',
        help='Run SCOTT news agent diagnostics'
    )
    parser.add_argument(
        '--penny-doctor',
        action='store_true',
        help='Run PENNY finance agent diagnostics'
    )
    parser.add_argument(
        '--sensei-doctor',
        action='store_true',
        help='Run SENSEI learning hub diagnostics'
    )
    parser.add_argument(
        '--echo-doctor',
        action='store_true',
        help='Run ECHO context hub diagnostics'
    )
    parser.add_argument(
        '--agents-doctor',
        action='store_true',
        help='Run diagnostics for all agents (SCOTT, PENNY, SENSEI, ECHO)'
    )

    # Learning command (v0.2.10)
    parser.add_argument(
        '--learn',
        nargs='?',
        const='all',
        metavar='TOPIC',
        help='Learn from SENSEI (optionally specify topic)'
    )

    # Finance command (v0.2.10)
    parser.add_argument(
        '--penny',
        nargs='+',
        metavar='QUERY',
        help='Query PENNY finance agent'
    )

    parser.add_argument(
        '--echo',
        nargs='+',
        metavar='QUERY',
        help='Query ECHO for context snippets'
    )

    return parser


def _normalize_cli_args(argv: list[str]) -> list[str]:
    normalized = []
    for arg in argv:
        if arg in ("gui--", "--gui--"):
            normalized.append("--gui")
        else:
            normalized.append(arg)
    return normalized


def check_ollama_health() -> int:
    """
    Check Ollama connectivity and model availability.
    
    Returns:
        Exit code (0 = healthy, 1 = unhealthy)
    """
    from .config import get_config
    from .llm_handler import LLMHandler
    
    config = get_config()
    
    print()
    print("═" * 55)
    print("  PANDA.1 Ollama Health Check")
    print("═" * 55)
    print()
    
    llm = LLMHandler()
    health = llm.health_check()
    
    # Connection status
    if health["connected"]:
        print(f"✓ Connected to Ollama at {health['url']}")
    else:
        print(f"✗ Cannot connect to Ollama at {health['url']}")
        if health["error"]:
            print(f"  Error: {health['error']}")
        print()
        print("To fix:")
        print("  1. Check if Ollama is running: systemctl status ollama")
        print("  2. Restart if needed: sudo systemctl restart ollama")
        print()
        print("═" * 55)
        return 1
    
    print()
    
    # Models
    if health["models"]:
        print("Models Available:")
        for model in health["models"]:
            # Mark primary and fallback
            markers = []
            if model == health["primary_model"] or model.startswith(health["primary_model"] + ":"):
                markers.append("primary")
            if model == health["fallback_model"] or model.startswith(health["fallback_model"].split(":")[0] + ":"):
                markers.append("fallback")
            
            marker_str = f" ({', '.join(markers)})" if markers else ""
            checkmark = "✓" if markers else " "
            print(f"  {checkmark} {model}{marker_str}")
    else:
        print("No models found!")
        print()
        print("To fix:")
        print(f"  ollama pull {config.llm_fallback_model}")
    
    print()
    
    # Overall status
    if health["healthy"]:
        print("Status: HEALTHY ✓")
        exit_code = 0
    else:
        print("Status: UNHEALTHY ✗")
        if not health["primary_model_available"] and not health["fallback_model_available"]:
            print()
            print("No usable model found. To fix:")
            print(f"  ollama pull {config.llm_fallback_model}")
        exit_code = 1
    
    print()
    print("═" * 55)
    
    return exit_code


def show_full_status() -> int:
    """Show comprehensive system status."""
    from .panda_core import PandaCore
    from .tts import get_tts_status
    
    config = get_config()
    
    print()
    print("═" * 55)
    print(f"  PANDA.1 v{__version__} System Status")
    print("═" * 55)
    print()
    
    # Configuration
    print("Configuration:")
    for key, value in config.to_display_dict().items():
        print(f"  {key}: {value}")
    print()
    
    # Component status
    try:
        panda = PandaCore()
        status = panda.get_status()
        
        print("Components:")
        
        # LLM
        llm = status.get("llm", {})
        if llm.get("healthy"):
            print(f"  ✓ LLM: Connected ({llm.get('active_model', 'unknown')})")
        else:
            print(f"  ✗ LLM: {llm.get('error', 'Offline')}")
        
        # OpenAI
        openai = status.get("openai")
        if openai:
            if openai.get("available"):
                print(f"  ✓ OpenAI: Available ({openai.get('model', 'unknown')})")
            else:
                print("  ○ OpenAI: Not configured")
        
        # Memory
        mem = status.get("memory")
        if mem:
            if mem.get("available"):
                print(f"  ✓ Memory: {mem.get('count', 0)} items stored")
            else:
                print("  ○ Memory: Disabled")
        else:
            print("  ○ Memory: Not configured")
        
        # SCOTT
        scott = status.get("scott")
        if scott:
            if scott.get("healthy"):
                print(f"  ✓ SCOTT: Connected ({config.scott_api_url})")
            else:
                print(f"  ✗ SCOTT: {scott.get('error', 'Offline')}")
        
        # PENNY
        penny = status.get("penny")
        if penny:
            if penny.get("healthy"):
                print(f"  ✓ PENNY: Connected ({config.penny_api_url})")
            else:
                print(f"  ○ PENNY: {penny.get('error', 'Offline')}")

        # ECHO
        echo = status.get("echo")
        if echo:
            if echo.get("healthy"):
                print(f"  ✓ ECHO: Connected ({config.echo_base_url})")
            else:
                print(f"  ○ ECHO: {echo.get('error', 'Offline')}")
        
        # TTS
        tts_status = get_tts_status()
        if tts_status.get("available"):
            engine = tts_status.get('engine', 'unknown')
            device = tts_status.get('device', 'cpu')
            print(f"  ✓ TTS: {engine.title()} ({device})")
        else:
            print("  ○ TTS: Not configured")
        
        # Mic status (new in v0.2.10)
        try:
            from .voice_assistant import list_audio_devices
            devices = list_audio_devices()
            input_count = len([d for d in devices if d.get('is_input')])
            if input_count > 0:
                print(f"  ✓ Microphone: {input_count} input device(s) available")
            else:
                print("  ✗ Microphone: No input devices found")
        except Exception:
            print("  ○ Microphone: Check with --audio-devices")
        
        print()
        print(f"Language Mode: {status.get('language', 'en').upper()}")
        
    except Exception as e:
        print(f"Error getting status: {e}")
    
    print()
    print("═" * 55)
    
    return 0


def show_config() -> int:
    """Show current configuration."""
    
    config = get_config()
    
    print()
    print("═" * 55)
    print("  PANDA.1 Configuration")
    print("═" * 55)
    print()
    
    for key, value in config.to_display_dict().items():
        print(f"  {key}: {value}")
    
    print()
    print(f"Config file: {config.base_dir / '.env'}")
    print()
    print("═" * 55)
    
    return 0


def run_interactive(console, debug: bool = False, stream: bool = True, initial_language: Optional[str] = None) -> int:
    """Run interactive CLI mode."""
    global _voice_enabled
    
    from .language_mode import get_language_manager, process_language_command
    from .tts import speak, is_tts_available
    
    panda = PandaCore()
    lang_manager = get_language_manager()
    tts_available = is_tts_available()
    
    # Set initial language if specified
    if initial_language:
        lang_manager.set_mode(initial_language)
    
    print()
    print("═" * 55)
    print("  PANDA.1 Interactive Mode (CLI)")
    print("═" * 55)
    print()
    print("Type /help for commands, /quit to exit")
    print(f"Language: {lang_manager.mode.upper()}")
    print(f"TTS: {'Available' if tts_available else 'Not available'}")
    print()
    
    while True:
        try:
            # Get input
            if console:
                console.print("[bold green]BOS:[/bold green] ", end="")
                user_input = input()
            else:
                user_input = input("BOS: ")
            
            if not user_input.strip():
                continue
            
            cmd = user_input.strip().lower()
            
            if cmd in ('/quit', '/exit', '/q'):
                print("Goodbye, BOS!")
                break
            
            if cmd == '/help':
                help_text = """
Commands:
  /quit, /exit    - Exit PANDA.1
  /help           - Show this help
  /status         - Show system status
  /cloud <query>  - Force OpenAI for this query
  /local <query>  - Force local LLM for this query
  /news [topic]   - Get news from SCOTT
  /penny <query>  - Query PENNY finance agent
  /sensei         - Show SENSEI status and categories
  /learn [topic]  - Learn from SENSEI (download to memory)
  /echo <query>   - Query ECHO for context snippets
  /agents         - Show all agent connection status
  /memory         - Memory stats
  /config         - Show configuration
  /voice on       - Enable TTS
  /voice off      - Disable TTS
  /lang en        - Switch to English
  /lang ko        - Switch to Korean

Natural language commands:
  "Panda, speak Korean"  - Switch to Korean output
  "Panda, speak English" - Switch to English output
  "판다, 한국어로 말해"    - Switch to Korean output
  "판다, 영어로 말해"      - Switch to English output
  "Panda learn"          - Learn from SENSEI
  "Ask Penny about..."   - Query PENNY finance

JNJ FOODS LLC queries (auto-routes to PENNY):
  "How is Mama Kim's doing?"
  "What's the monthly revenue?"
  "Show me the P&L"
                """
                print(help_text)
                continue
            
            if cmd == '/voice on':
                _voice_enabled = True
                if tts_available:
                    print("Voice enabled.")
                    speak("Voice enabled.", block=True)
                else:
                    print("Voice enabled, but TTS not available.")
                continue
            
            if cmd == '/voice off':
                _voice_enabled = False
                print("Voice disabled.")
                continue
            
            if cmd == '/voice':
                status = "enabled" if _voice_enabled else "disabled"
                available = "available" if tts_available else "not available"
                print(f"Voice: {status} (TTS {available})")
                continue
            
            if cmd == '/status':
                show_full_status()
                continue
            
            if cmd == '/config':
                show_config()
                continue
            
            if cmd == '/lang en':
                lang_manager.set_mode("en")
                print("Language mode: English")
                if tts_available and _voice_enabled:
                    speak("Now speaking in English.", block=True)
                continue
            
            if cmd == '/lang ko':
                lang_manager.set_mode("ko")
                print("Language mode: Korean (한국어)")
                if tts_available and _voice_enabled:
                    speak("이제 한국어로 말할게요.", block=True)
                continue
            
            if cmd.startswith('/news'):
                parts = user_input.split(maxsplit=1)
                topic = parts[1] if len(parts) > 1 else None
                response = panda._handle_news_intent(f"news {topic or ''}")
                print(f"\n{response}\n")
                if _voice_enabled and tts_available:
                    speak(response, block=True)
                continue
            
            if cmd.startswith('/penny'):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: /penny <your question>")
                    continue
                query = parts[1]
                response = panda._handle_penny_intent(query)
                print(f"\n{response}\n")
                if _voice_enabled and tts_available:
                    speak(response, block=True)
                continue

            if cmd == '/sensei':
                if panda.sensei_client:
                    health = panda.sensei_client.health_check()
                    if health.get("healthy"):
                        print("\nSENSEI Status: Connected")
                        categories = panda.sensei_client.get_categories()
                        if categories:
                            print(f"Categories: {', '.join(categories)}")
                        lessons = panda.sensei_client.get_lessons(limit=5)
                        if lessons.get("success") and lessons.get("lessons"):
                            print(f"Recent lessons available: {len(lessons['lessons'])}")
                    else:
                        print(f"\nSENSEI Status: Offline ({health.get('error', 'Unknown')})")
                else:
                    print("\nSENSEI is not configured.")
                print()
                continue

            if cmd.startswith('/learn'):
                parts = user_input.split(maxsplit=1)
                topic = parts[1] if len(parts) > 1 else None
                if topic:
                    response = panda._handle_sensei_learning(f"learn from sensei about {topic}")
                else:
                    response = panda._handle_sensei_learning("learn from sensei")
                print(f"\n{response}\n")
                if _voice_enabled and tts_available:
                    speak(response, block=True)
                continue

            if cmd.startswith('/echo'):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print("Usage: /echo <your question>")
                    continue
                query = parts[1]
                response = panda._handle_echo_query(query)
                print(f"\n{response}\n")
                if _voice_enabled and tts_available:
                    speak(response, block=True)
                continue

            if cmd == '/agents':
                print("\nAgent Status:")
                # SCOTT
                if panda.scott_client:
                    if panda.scott_client.is_healthy():
                        print(f"  SCOTT: Connected ({panda.config.scott_api_url})")
                    else:
                        print(f"  SCOTT: Offline")
                else:
                    print("  SCOTT: Not configured")
                # PENNY
                if panda.penny_client:
                    if panda.penny_client.is_healthy():
                        print(f"  PENNY: Connected ({panda.config.penny_api_url})")
                    else:
                        print(f"  PENNY: Offline")
                else:
                    print("  PENNY: Not configured")
                # SENSEI
                if panda.sensei_client:
                    if panda.sensei_client.is_healthy():
                        print(f"  SENSEI: Connected ({panda.config.sensei_api_url})")
                    else:
                        print(f"  SENSEI: Offline")
                else:
                    print("  SENSEI: Not configured")
                # ECHO
                if panda.echo_client:
                    if panda.echo_client.is_healthy():
                        print(f"  ECHO: Connected ({panda.config.echo_base_url})")
                    else:
                        print("  ECHO: Offline")
                else:
                    print("  ECHO: Not configured")
                print()
                continue

            if cmd == '/memory':
                if panda.memory and panda.memory.is_available:
                    status = panda.memory.get_status()
                    print(f"\nMemory: {status.get('count', 0)} items stored")
                    print(f"Collection: {status.get('collection', 'unknown')}\n")
                else:
                    print("\nMemory system not available.\n")
                continue
            
            # Process regular chat
            if stream:
                # Streaming response
                if console:
                    console.print("[bold cyan]PANDA.1:[/bold cyan] ", end="")
                else:
                    print("PANDA.1: ", end="")
                
                full_response = ""
                for chunk in panda.process_stream(user_input):
                    print(chunk, end="", flush=True)
                    full_response += chunk
                print("\n")
                
                if _voice_enabled and tts_available and full_response.strip():
                    speak(full_response, block=True)
            else:
                # Non-streaming
                response = panda.process(user_input)
                if console:
                    console.print(f"[bold cyan]PANDA.1:[/bold cyan] {response}")
                else:
                    print(f"PANDA.1: {response}")
                print()
                
                if _voice_enabled and tts_available and response.strip():
                    speak(response, block=True)
            
        except KeyboardInterrupt:
            print("\n[Use /quit to exit]")
            continue
        except EOFError:
            break
    
    return 0


def run_gui(port: Optional[int] = None) -> int:
    """Launch the web GUI."""
    try:
        from .web_gui import run_server
        if port is None:
            return run_server()
        return run_server(port=port)
    except ImportError as e:
        print(f"GUI not available: {e}")
        print("Install: pip install fastapi uvicorn")
        return 1


def run_voice() -> int:
    """Start voice assistant mode with wake phrase detection."""
    print()
    print("═" * 55)
    print("  PANDA.1 Voice Assistant")
    print("═" * 55)
    print()
    print("Starting voice assistant mode...")
    print("Wake phrases: 'Hey Panda' or 'Yo Panda'")
    print("Press Ctrl+C to exit")
    print()
    
    try:
        from .voice_assistant import run_voice_assistant
        return run_voice_assistant()
    except ImportError as e:
        print(f"Voice assistant not available: {e}")
        print()
        print("Required packages:")
        print("  pip install openai-whisper sounddevice soundfile")
        print("  pip install webrtcvad  # optional, for better VAD")
        return 1
    except Exception as e:
        print(f"Error starting voice assistant: {e}")
        return 1


def run_single_query(query: str, console) -> int:
    """Process a single query and exit."""
    
    panda = PandaCore()
    response = panda.process(query)
    
    if console:
        console.print(f"[bold cyan]PANDA.1:[/bold cyan] {response}")
    else:
        print(f"PANDA.1: {response}")
    
    return 0


def run_api(port: Optional[int]) -> int:
    """Start the API server."""
    try:
        from .api_server import start_server
        if port is None:
            from .config import get_config
            port = get_config().api_port
        return start_server(port=port)
    except ImportError as e:
        print(f"API server not available: {e}")
        print("Install: pip install fastapi uvicorn")
        return 1


def run_doctor() -> int:
    """
    Run TTS diagnostics and show fix steps.
    
    Returns:
        Exit code (0 = healthy, 1 = issues found)
    """
    import shutil
    from pathlib import Path
    
    print()
    print("═" * 60)
    print("  PANDA.1 Doctor - TTS Diagnostics")
    print("═" * 60)
    print()
    
    issues = []
    
    # 1. Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"Python Version: {py_version}")
    if sys.version_info >= (3, 12):
        print("  ⚠ Python 3.12+ detected - may have Chatterbox compatibility issues")
        issues.append("Consider using Python 3.11 for better Chatterbox compatibility")
    elif sys.version_info < (3, 10):
        print("  ✗ Python 3.10+ required")
        issues.append("Upgrade to Python 3.10 or later")
    else:
        print("  ✓ Python version OK")
    
    # 2. Venv path
    venv_path = Path(sys.prefix)
    print(f"\nVenv Path: {venv_path}")
    
    # 3. Torch / CUDA
    print("\nTorch Status:")
    try:
        import torch
        print(f"  torch version: {torch.__version__}")
        if torch.cuda.is_available():
            print(f"  ✓ CUDA available: {torch.cuda.get_device_name(0)}")
            print(f"  CUDA version: {torch.version.cuda}")
        else:
            print("  ⚠ CUDA not available - using CPU")
    except ImportError:
        print("  ✗ torch not installed")
        issues.append("Install PyTorch: pip install torch torchaudio")
    
    # 4. Chatterbox
    print("\nChatterbox Status:")
    try:
        import chatterbox
        version = getattr(chatterbox, "__version__", "unknown")
        print(f"  ✓ chatterbox-tts version: {version}")
        
        # Check if models are cached
        cache_dir = Path.home() / ".panda1" / "cache" / "huggingface"
        if cache_dir.exists() and any(cache_dir.iterdir()):
            print(f"  ✓ Models cached at: {cache_dir}")
        else:
            print(f"  ⚠ No cached models found")
            issues.append("Run: panda --tts-prefetch to download models")
            
    except ImportError as e:
        print(f"  ✗ chatterbox-tts not installed: {e}")
        issues.append("Install Chatterbox: pip install chatterbox-tts")
    
    # 5. Audio player
    print("\nAudio Player:")
    players = ["aplay", "paplay", "ffplay", "play"]
    found_player = None
    for player in players:
        if shutil.which(player):
            found_player = player
            print(f"  ✓ Found: {player}")
            break
    
    if not found_player:
        print("  ✗ No audio player found!")
        issues.append("Install audio player: sudo apt install alsa-utils")
    
    # 6. TTS Engine
    print("\nTTS Engine Status:")
    try:
        from app.panda_tts import get_tts_manager
        manager = get_tts_manager()
        manager.initialize()
        
        health = manager.healthcheck()
        print(f"  Engine: {health.get('engine', 'unknown')}")
        print(f"  Device: {health.get('device', 'unknown')}")
        print(f"  Healthy: {'✓' if health.get('healthy') else '✗'}")
        
        if health.get('error'):
            print(f"  Error: {health['error']}")
            issues.append(f"TTS Error: {health['error']}")
            
    except Exception as e:
        print(f"  ✗ Failed to initialize TTS: {e}")
        issues.append(f"TTS init failed: {e}")
    
    # Summary
    print()
    print("═" * 60)
    if issues:
        print("  Issues Found:")
        print("═" * 60)
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        print("Fix Steps:")
        print("  1. Ensure Python 3.11 is installed")
        print("  2. pip install torch torchaudio chatterbox-tts")
        print("  3. panda --tts-prefetch")
        print("  4. panda --tts-test")
        return 1
    else:
        print("  ✓ All TTS systems healthy!")
        print("═" * 60)
        return 0


def run_gui_doctor() -> int:
    """
    Run GUI-specific diagnostics (v0.2.10).
    
    Checks:
    - WebSocket endpoint reachable
    - Action log POST health (200 not 422)
    - Voice enabled? Mic available? Device index valid?
    - TTS engine OK? Playback command available?
    - LLM endpoint OK (Ollama)
    - Memory OK (Chroma path)
    - SCOTT status
    
    Returns:
        Exit code (0 = healthy, 1 = issues found)
    """
    
    print()
    print("═" * 60)
    print("  PANDA.1 v0.2.11 GUI Doctor")
    print("═" * 60)
    print()
    
    issues = []
    fixes = []
    
    # Load config
    try:
        config = get_config()
        print(f"Config loaded from: {config.base_dir}")
    except Exception as e:
        print(f"✗ Failed to load config: {e}")
        issues.append("Config load failed")
        fixes.append("Ensure ~/.panda1/.env exists and is valid")
        config = None
    
    # 1. Check Ollama/LLM
    print("\n1. LLM (Ollama):")
    try:
        llm = LLMHandler()
        health = llm.health_check()
        if health["connected"]:
            print(f"  ✓ Connected to {health['url']}")
            if health["healthy"]:
                print(f"  ✓ Model available: {health.get('primary_model', 'unknown')}")
            else:
                print("  ✗ No usable model found")
                issues.append("LLM: No model available")
                fixes.append(f"Run: ollama pull {config.llm_fallback_model if config else 'qwen2.5:7b-instruct-q4_K_M'}")
        else:
            print(f"  ✗ Cannot connect to Ollama at {health['url']}")
            issues.append("LLM: Ollama not reachable")
            fixes.append("Check Ollama: systemctl status ollama")
    except Exception as e:
        print(f"  ✗ LLM check failed: {e}")
        issues.append(f"LLM check error: {e}")
    
    # 2. Check Memory (Chroma)
    print("\n2. Memory (ChromaDB):")
    try:
        from .memory import MemorySystem
        mem = MemorySystem()
        if mem.is_available:
            status = mem.get_status()
            print(f"  ✓ ChromaDB available ({status.get('count', 0)} items)")
        else:
            print("  ○ Memory disabled or unavailable")
    except Exception as e:
        print(f"  ○ Memory not configured: {e}")
    
    # 3. Check TTS
    print("\n3. TTS Engine:")
    try:
        manager = get_tts_manager()
        manager.initialize()
        health = manager.healthcheck()
        
        if health.get("healthy"):
            print(f"  ✓ {health.get('engine', 'unknown').title()} ready ({health.get('device', 'cpu')})")
        else:
            print(f"  ✗ TTS unhealthy: {health.get('error', 'unknown')}")
            issues.append("TTS not healthy")
            fixes.append("Run: panda --doctor for TTS diagnostics")
    except Exception as e:
        print(f"  ✗ TTS init failed: {e}")
        issues.append("TTS initialization failed")
        fixes.append("Run: panda --doctor")
    
    # 4. Check Audio Playback
    print("\n4. Audio Playback:")
    players = ["aplay", "paplay", "ffplay", "play"]
    found_player = None
    for player in players:
        if shutil.which(player):
            found_player = player
            break
    
    if found_player:
        print(f"  ✓ Player found: {found_player}")
        if config and config.alsa_device:
            print(f"  ○ ALSA device: {config.alsa_device}")
    else:
        print("  ✗ No audio player found")
        issues.append("No audio playback command")
        fixes.append("Install: sudo apt install alsa-utils")
    
    # 5. Check Microphone / Voice Input
    print("\n5. Microphone / Voice Input:")
    try:
        devices = list_audio_devices()
        inputs = [d for d in devices if d.get('is_input')]
        
        if inputs:
            print(f"  ✓ {len(inputs)} input device(s) found")
            
            # Check configured device
            if config and config.audio_input_device is not None:
                dev_idx = config.audio_input_device
                matching = [d for d in inputs if d.get('index') == dev_idx]
                if matching:
                    print(f"  ✓ Configured device #{dev_idx}: {matching[0].get('name', 'unknown')}")
                else:
                    print(f"  ⚠ Configured device #{dev_idx} not found in input devices")
                    issues.append(f"Audio input device #{dev_idx} not found")
                    fixes.append("Check with: panda --audio-devices")
            else:
                # Show default
                default = next((d for d in inputs if d.get('is_default')), None)
                if default:
                    print(f"  ○ Using default: {default.get('name', 'unknown')}")
        else:
            print("  ✗ No input devices found")
            issues.append("No microphone available")
            fixes.append("Connect a microphone and check: panda --audio-devices")
            
    except ImportError:
        print("  ○ Voice assistant module not available")
        print("    Install: pip install sounddevice soundfile openai-whisper")
    except Exception as e:
        print(f"  ⚠ Could not list devices: {e}")
    
    # 6. Check GUI Voice Config
    print("\n6. GUI Voice Config:")
    if config:
        print(f"  GUI Voice Enabled: {config.gui_voice_enabled}")
        print(f"  Voice Ack Enabled: {config.voice_ack_enabled}")
        if config.audio_input_device is not None:
            print(f"  Audio Input Device: {config.audio_input_device}")
        else:
            print("  Audio Input Device: (system default)")
    else:
        print("  ○ Config not loaded")
    
    # 7. Check SCOTT
    print("\n7. SCOTT News Agent:")
    if config and config.scott_enabled:
        try:
            from .scott_client import ScottClient
            scott = ScottClient()
            if scott.health_check():
                print(f"  ✓ Connected to {config.scott_api_url}")
            else:
                print(f"  ○ SCOTT offline at {config.scott_api_url}")
                print("    (This is OK - GUI works without SCOTT)")
        except Exception as e:
            print(f"  ○ SCOTT not reachable: {e}")
    else:
        print("  ○ SCOTT disabled in config")
    
    # 8. WebSocket / GUI Server test
    print("\n8. GUI Server Components:")
    try:
        import fastapi
        import uvicorn
        print(f"  ✓ FastAPI: {fastapi.__version__}")
        print(f"  ✓ Uvicorn: {uvicorn.__version__}")
    except ImportError as e:
        print(f"  ✗ Missing: {e}")
        issues.append("FastAPI/Uvicorn not installed")
        fixes.append("Install: pip install fastapi uvicorn")
    
    # Summary
    print()
    print("═" * 60)
    if issues:
        print("  Issues Found:")
        print("═" * 60)
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        print("Fix Steps:")
        for i, fix in enumerate(fixes, 1):
            print(f"  {i}. {fix}")
        return 1
    else:
        print("  ✓ All GUI systems healthy!")
        print("═" * 60)
        print()
        print("Start GUI with: panda")
        print("Then open: http://127.0.0.1:7860")
        return 0


def run_audio_devices() -> int:
    """
    List all audio devices (INPUT and OUTPUT) with indices.
    Enhanced in v0.2.10 to show microphone inputs for voice wake.
    
    Returns:
        Exit code (0 = success)
    """
    print()
    print("═" * 60)
    print("  PANDA.1 Audio Devices")
    print("═" * 60)
    
    # Try sounddevice first (primary for voice input)
    print("\n─── sounddevice (Voice Input/Output) ───")
    try:
        from .voice_assistant import print_audio_devices
        print_audio_devices()
    except ImportError:
        try:
            import sounddevice as sd
            print("\nInput Devices:")
            devices = sd.query_devices()
            default_input = sd.default.device[0]
            default_output = sd.default.device[1]
            
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    default_mark = " [DEFAULT INPUT]" if i == default_input else ""
                    print(f"  [{i}] {dev['name']} ({dev['max_input_channels']}ch){default_mark}")
            
            print("\nOutput Devices:")
            for i, dev in enumerate(devices):
                if dev['max_output_channels'] > 0:
                    default_mark = " [DEFAULT OUTPUT]" if i == default_output else ""
                    print(f"  [{i}] {dev['name']} ({dev['max_output_channels']}ch){default_mark}")
                    
        except ImportError:
            print("  sounddevice not installed")
            print("  Install: pip install sounddevice")
        except Exception as e:
            print(f"  Error: {e}")
    
    # Also show ALSA for playback config
    print("\n─── ALSA Playback Devices (aplay -l) ───")
    try:
        import subprocess
        result = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            # Parse and show devices
            for line in result.stdout.split('\n'):
                if line.startswith('card') or 'Subdevices' in line:
                    print(f"  {line}")
        else:
            print("  No ALSA devices or aplay not available")
    except FileNotFoundError:
        print("  aplay not installed (sudo apt install alsa-utils)")
    except Exception as e:
        print(f"  Error: {e}")
    
    # Config hint
    print()
    print("─── Configuration ───")
    try:
        config = get_config()
        print(f"  PANDA_AUDIO_INPUT_DEVICE: {config.audio_input_device or '(not set - using default)'}")
        print(f"  PANDA_ALSA_DEVICE: {config.alsa_device}")
    except Exception as e:
        logging.error(f'Exception caught: {e}')
        print("  Set in ~/.panda1/.env:")
        print("    PANDA_AUDIO_INPUT_DEVICE=<index>  # for mic input")
        print("    PANDA_ALSA_DEVICE=<device>        # for playback")
    
    print()
    print("═" * 60)
    return 0


def run_mic_test(duration: int = 3) -> int:
    """
    Test microphone input by recording and analyzing audio levels.
    
    Args:
        duration: Seconds to record (default: 3)
    
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print()
    print("═" * 60)
    print("  PANDA.1 Microphone Test")
    print("═" * 60)
    print()
    
    try:
        from .voice_assistant import mic_test
        
        config = get_config()
        device_idx = config.audio_input_device
        
        if device_idx is not None:
            print(f"Using configured device index: {device_idx}")
        else:
            print("Using system default input device")
        
        print(f"Recording {duration} seconds...")
        print()
        
        result = mic_test(duration=duration, save_wav=True)
        
        if result:
            print(f"  RMS Level:  {result.get('rms', 0):.4f}")
            print(f"  Peak Level: {result.get('peak', 0):.4f}")
            print(f"  Duration:   {result.get('duration', 0):.2f}s")
            
            if result.get('wav_path'):
                print(f"  Saved to:   {result['wav_path']}")
            
            # Interpret levels
            rms = result.get('rms', 0)
            print()
            if rms < 0.001:
                print("  ⚠ Level very low - check if mic is muted or unplugged")
            elif rms < 0.01:
                print("  ○ Level low - speak louder or move closer to mic")
            elif rms > 0.5:
                print("  ⚠ Level very high - may be clipping, move away from mic")
            else:
                print("  ✓ Level looks good!")
            
            return 0
        else:
            print("  ✗ Mic test failed - no audio captured")
            return 1
            
    except ImportError as e:
        print(f"✗ Voice assistant module not available: {e}")
        print()
        print("Install required packages:")
        print("  pip install sounddevice soundfile numpy")
        return 1
    except Exception as e:
        print(f"✗ Mic test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_tts_test(text: str) -> int:
    """
    Test TTS by synthesizing and playing text.
    
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print()
    print("═" * 55)
    print("  PANDA.1 TTS Test")
    print("═" * 55)
    print()
    
    try:
        
        print(f"Text: {text}")
        print()
        
        manager = get_tts_manager()
        print("Initializing TTS engine...")
        manager.initialize()
        
        health = manager.healthcheck()
        print(f"Engine: {health.get('engine', 'unknown')}")
        print(f"Device: {health.get('device', 'unknown')}")
        print()
        
        # Synthesize
        print("Synthesizing...")
        audio_path = manager.synthesize(text)
        
        if audio_path and audio_path.exists():
            print(f"✓ Audio saved: {audio_path}")
            print()
            print("Playing...")
            
            # Play with blocking
            manager.speak(text, blocking=True)
            
            print()
            print("✓ TTS test passed!")
            return 0
        else:
            print("✗ Synthesis failed - no audio generated")
            return 1
            
    except Exception as e:
        print(f"✗ TTS test failed: {e}")
        traceback.print_exc()
        return 1


def run_scott_doctor() -> int:
    """Run SCOTT news agent diagnostics."""
    try:
        from .integrations.scott_client import print_scott_doctor
        print_scott_doctor()
        return 0
    except ImportError as e:
        print(f"SCOTT client not available: {e}")
        return 1
    except Exception as e:
        print(f"Error running SCOTT diagnostics: {e}")
        return 1


def run_penny_doctor() -> int:
    """Run PENNY finance agent diagnostics."""

    print()
    print("═" * 60)
    print("  PANDA.1 PENNY Doctor")
    print("═" * 60)
    print()

    config = get_config()
    results = []

    # Check if enabled
    if config.penny_enabled:
        print(f"  PANDA_PENNY_ENABLED: True")
    else:
        print(f"  PANDA_PENNY_ENABLED: False")
        print("\n  PENNY is disabled. Enable with PANDA_PENNY_ENABLED=true")
        return 0

    # Check URL
    print(f"  PANDA_PENNY_API_URL: {config.penny_api_url}")

    # Try to connect
    try:
        from .penny_client import PennyClient
        client = PennyClient(
            base_url=config.penny_api_url,
            timeout=config.penny_timeout
        )

        health = client.health_check()

        if health.get("healthy"):
            print(f"\n  TCP/HTTP: Connected")
            print(f"  Health check: OK")
            if health.get("data"):
                print(f"  Server info: {health.get('data')}")
            print("\n" + "=" * 60)
            print("  Overall: OK")
        else:
            print(f"\n  Health check: FAILED")
            print(f"  Error: {health.get('error', 'Unknown')}")
            print("\n  Common fixes:")
            print("  - Ensure PENNY is running on the target machine")
            print(f"  - Check if {config.penny_api_url} is reachable")
            print("  - Verify firewall allows connections")
            print("\n" + "=" * 60)
            print("  Overall: ERROR")
            return 1

    except Exception as e:
        print(f"\n  Connection failed: {e}")
        print("\n" + "=" * 60)
        print("  Overall: ERROR")
        return 1

    print()
    return 0


def run_sensei_doctor() -> int:
    """Run SENSEI learning hub diagnostics."""

    print()
    print("═" * 60)
    print("  PANDA.1 SENSEI Doctor")
    print("═" * 60)
    print()

    config = get_config()

    # Check if enabled
    if config.sensei_enabled:
        print(f"  PANDA_SENSEI_ENABLED: True")
    else:
        print(f"  PANDA_SENSEI_ENABLED: False")
        print("\n  SENSEI is disabled. Enable with PANDA_SENSEI_ENABLED=true")
        return 0

    # Check URL
    print(f"  PANDA_SENSEI_API_URL: {config.sensei_api_url}")

    # Try to connect
    try:
        from .sensei_client import SenseiClient
        client = SenseiClient(
            base_url=config.sensei_api_url,
            timeout=config.sensei_timeout
        )

        health = client.health_check()

        if health.get("healthy"):
            print(f"\n  TCP/HTTP: Connected")
            print(f"  Health check: OK")
            if health.get("data"):
                print(f"  Server info: {health.get('data')}")

            # Try to get categories
            categories = client.get_categories()
            if categories:
                print(f"  Categories: {', '.join(categories[:5])}")
                if len(categories) > 5:
                    print(f"    ... and {len(categories) - 5} more")

            # Try to get lesson count
            lessons = client.get_lessons(limit=1)
            if lessons.get("success"):
                print(f"  Lessons available: Yes")

            print("\n" + "=" * 60)
            print("  Overall: OK")
        else:
            print(f"\n  Health check: FAILED")
            print(f"  Error: {health.get('error', 'Unknown')}")
            print("\n  Common fixes:")
            print("  - Ensure SENSEI is running on 192.168.1.19:8002")
            print(f"  - Check if {config.sensei_api_url} is reachable")
            print("  - Verify LAN connectivity")
            print("\n" + "=" * 60)
            print("  Overall: ERROR")
            return 1

    except Exception as e:
        print(f"\n  Connection failed: {e}")
        print("\n" + "=" * 60)
        print("  Overall: ERROR")
        return 1

    print()
    return 0


def run_echo_doctor() -> int:
    """Run ECHO context hub diagnostics."""

    print()
    print("═" * 60)
    print("  PANDA.1 ECHO Doctor")
    print("═" * 60)
    print()

    config = get_config()

    if config.echo_enabled:
        print("  PANDA_ECHO_ENABLED: True")
    else:
        print("  PANDA_ECHO_ENABLED: False")
        print("\n  ECHO is disabled. Enable with PANDA_ECHO_ENABLED=true")
        return 0

    print(f"  PANDA_ECHO_BASE_URL: {config.echo_base_url}")

    try:
        from .echo_client import EchoClient
        client = EchoClient(
            base_url=config.echo_base_url,
            timeout=config.echo_timeout,
            api_key=config.echo_api_key or None,
        )
        health = client.health_check()

        if health.get("healthy"):
            print("\n  TCP/HTTP: Connected")
            print("  Health check: OK")
            if health.get("data"):
                print(f"  Server info: {health.get('data')}")
            print("\n" + "=" * 60)
            print("  Overall: OK")
        else:
            print("\n  Health check: FAILED")
            print(f"  Error: {health.get('error', 'Unknown')}")
            print("\n  Common fixes:")
            print("  - Ensure ECHO server is running on the database PC")
            print(f"  - Check if {config.echo_base_url} is reachable")
            print("  - Verify firewall allows connections")
            print("\n" + "=" * 60)
            print("  Overall: ERROR")
            return 1

    except Exception as e:
        print(f"\n  Connection failed: {e}")
        print("\n" + "=" * 60)
        print("  Overall: ERROR")
        return 1

    print()
    return 0


def run_agents_doctor() -> int:
    """Run diagnostics for all agents."""
    print()
    print("═" * 60)
    print("  PANDA.1 All Agents Doctor")
    print("═" * 60)

    results = []

    # SCOTT
    print("\n--- SCOTT News Agent ---")
    try:
        from .integrations.scott_client import scott_doctor
        scott_result = scott_doctor()
        results.append(("SCOTT", scott_result.get("overall", "unknown")))
        for check in scott_result.get("checks", []):
            status_icon = {"ok": "", "warning": "", "error": ""}.get(check["status"], "?")
            print(f"  {status_icon} {check['name']}: {check['message']}")
    except Exception as e:
        print(f"  Error: {e}")
        results.append(("SCOTT", "error"))

    # PENNY
    print("\n--- PENNY Finance Agent ---")
    try:
        config = get_config()
        if config.penny_enabled:
            from .penny_client import PennyClient
            client = PennyClient(base_url=config.penny_api_url, timeout=config.penny_timeout)
            health = client.health_check()
            if health.get("healthy"):
                print(f"  Connected to {config.penny_api_url}")
                results.append(("PENNY", "ok"))
            else:
                print(f"  Offline: {health.get('error', 'Unknown')}")
                results.append(("PENNY", "error"))
        else:
            print("  Disabled")
            results.append(("PENNY", "disabled"))
    except Exception as e:
        print(f"  Error: {e}")
        results.append(("PENNY", "error"))

    # SENSEI
    print("\n--- SENSEI Learning Hub ---")
    try:
        config = get_config()
        if config.sensei_enabled:
            from .sensei_client import SenseiClient
            client = SenseiClient(base_url=config.sensei_api_url, timeout=config.sensei_timeout)
            health = client.health_check()
            if health.get("healthy"):
                print(f"  Connected to {config.sensei_api_url}")
                results.append(("SENSEI", "ok"))
            else:
                print(f"  Offline: {health.get('error', 'Unknown')}")
                results.append(("SENSEI", "error"))
        else:
            print("  Disabled")
            results.append(("SENSEI", "disabled"))
    except Exception as e:
        print(f"  Error: {e}")
        results.append(("SENSEI", "error"))

    # ECHO
    print("\n--- ECHO Context Hub ---")
    try:
        config = get_config()
        if config.echo_enabled:
            from .echo_client import EchoClient
            client = EchoClient(
                base_url=config.echo_base_url,
                timeout=config.echo_timeout,
                api_key=config.echo_api_key or None,
            )
            health = client.health_check()
            if health.get("healthy"):
                print(f"  Connected to {config.echo_base_url}")
                results.append(("ECHO", "ok"))
            else:
                print(f"  Offline: {health.get('error', 'Unknown')}")
                results.append(("ECHO", "error"))
        else:
            print("  Disabled")
            results.append(("ECHO", "disabled"))
    except Exception as e:
        print(f"  Error: {e}")
        results.append(("ECHO", "error"))

    # Summary
    print()
    print("═" * 60)
    print("  Summary:")
    for name, status in results:
        icon = {"ok": "", "warning": "", "error": "", "disabled": ""}.get(status, "?")
        print(f"    {icon} {name}: {status.upper()}")
    print("═" * 60)
    print()

    return 0 if all(r[1] in ("ok", "disabled") for r in results) else 1


def run_learn(topic: str = None) -> int:
    """Learn from SENSEI."""

    print()
    print("═" * 60)
    print("  PANDA.1 Learning from SENSEI")
    print("═" * 60)
    print()

    config = get_config()

    if not config.sensei_enabled:
        print("SENSEI is disabled. Enable with PANDA_SENSEI_ENABLED=true")
        return 1

    try:
        panda = PandaCore()

        if topic and topic != "all":
            print(f"Learning topic: {topic}")
            query = f"learn from sensei about {topic}"
        else:
            print("Learning all available content...")
            query = "learn from sensei"

        print()
        response = panda._handle_sensei_learning(query)
        print(response)
        print()
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_penny_query(query: str) -> int:
    """Query PENNY finance agent."""

    print()

    config = get_config()

    if not config.penny_enabled:
        print("PENNY is disabled. Enable with PANDA_PENNY_ENABLED=true")
        return 1

    try:
        panda = PandaCore()
        response = panda._handle_penny_intent(query)
        print(f"PENNY: {response}")
        print()
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_echo_query(query: str) -> int:
    """Query ECHO for context snippets."""

    print()

    config = get_config()

    if not config.echo_enabled:
        print("ECHO is disabled. Enable with PANDA_ECHO_ENABLED=true")
        return 1

    try:
        panda = PandaCore()
        response = panda._handle_echo_query(query)
        print(f"ECHO: {response}")
        print()
        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def run_tts_prefetch() -> int:
    """
    Download and cache TTS models for offline use.

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print()
    print("═" * 55)
    print("  PANDA.1 TTS Model Prefetch")
    print("═" * 55)
    print()
    
    try:
        from app.panda_tts.chatterbox_engine import ChatterboxEngine
        
        cache_dir = Path.home() / ".panda1" / "cache" / "huggingface"
        print(f"Cache directory: {cache_dir}")
        print()
        
        print("Downloading Chatterbox models...")
        print("This may take several minutes on first run.")
        print()
        
        engine = ChatterboxEngine(cache_dir=cache_dir)
        
        if engine.prefetch_models():
            print()
            print("✓ Models prefetched successfully!")
            print("You can now use PANDA.1 offline.")
            return 0
        else:
            print("✗ Model prefetch failed")
            return 1
            
    except ImportError as e:
        print(f"✗ Chatterbox not installed: {e}")
        print()
        print("Install with: pip install chatterbox-tts")
        return 1
    except Exception as e:
        print(f"✗ Prefetch failed: {e}")
        traceback.print_exc()
        return 1


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(_normalize_cli_args(sys.argv[1:]))
    
    # Setup debug logging
    if args.debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    # Try to use Rich for better output
    console = None
    try:
        from rich.console import Console
        console = Console()
    except ImportError:
        pass
    
    # Health check mode
    if args.check_ollama:
        return check_ollama_health()
    
    # Status mode
    if args.status:
        return show_full_status()
    
    # Config display
    if args.config:
        return show_config()
    
    # TTS diagnostics (doctor)
    if args.doctor:
        return run_doctor()
    
    # GUI diagnostics (new in v0.2.10)
    if args.gui_doctor:
        return run_gui_doctor()

    # Agent diagnostics (v0.2.10)
    if args.scott_doctor:
        return run_scott_doctor()

    if args.penny_doctor:
        return run_penny_doctor()

    if args.sensei_doctor:
        return run_sensei_doctor()

    if args.echo_doctor:
        return run_echo_doctor()

    if args.agents_doctor:
        return run_agents_doctor()

    # Learning from SENSEI (v0.2.10)
    if args.learn is not None:
        topic = args.learn if args.learn != 'all' else None
        return run_learn(topic)

    # Query PENNY (v0.2.10)
    if args.penny:
        query = " ".join(args.penny)
        return run_penny_query(query)

    # Query ECHO
    if args.echo:
        query = " ".join(args.echo)
        return run_echo_query(query)

    # TTS test
    if args.tts_test:
        return run_tts_test(args.tts_test)
    
    # TTS model prefetch
    if args.tts_prefetch:
        return run_tts_prefetch()
    
    # Audio devices listing (enhanced in v0.2.10)
    if args.audio_devices:
        return run_audio_devices()
    
    # Audio test
    if args.audio_test:
        from app.panda_tts.playback import test_audio_playback
        success = test_audio_playback()
        return 0 if success else 1
    
    # Mic test (new in v0.2.10)
    if args.mic_test is not None:
        return run_mic_test(args.mic_test)
    
    # News mode
    if args.news:
        panda = PandaCore()
        topic = args.news if args.news != 'top' else None
        response = panda._handle_news_intent(f"news {topic or ''}")
        print(response)
        return 0
    
    # Single query mode
    if args.query:
        query = " ".join(args.query)
        return run_single_query(query, console)
    
    # CLI mode (explicit)
    if args.cli:
        stream = not args.no_stream
        return run_interactive(console, debug=args.debug, stream=stream, initial_language=args.language)
    
    # API mode
    if args.api:
        return run_api(args.port)
    
    # Voice assistant mode
    if args.voice:
        return run_voice()
    
    # GUI mode (explicit or DEFAULT)
    # If no mode specified, default to GUI
    return run_gui(args.port)


if __name__ == '__main__':
    sys.exit(main())
