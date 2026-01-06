"""
PANDA.1 Configuration
=====================
Central configuration for all PANDA.1 components.

Version: 0.2.11

Network Configuration:
- Ollama host: PANDA_OLLAMA_HOST (default: http://localhost:11434)
- SCOTT news: SCOTT_BASE_URL (default: http://192.168.1.18:8000)
- GUI binds to 127.0.0.1:7860 for local kiosk usage

Voice Configuration (NEW in v0.2.10):
- Faster-Whisper STT with EN/KO/AUTO modes
- Kokoro TTS with lightweight offline synthesis
- PTT via Space bar or mic button
- Language mode: Auto / English / Korean

OpenAI Fallback (NEW in v0.2.10):
- OPENAI_FALLBACK_ENABLED: Enable GPT-4 fallback
- OPENAI_API_KEY: Your API key (never exposed to frontend)
- OPENAI_CONFIDENCE_THRESHOLD: Trigger threshold (default: 0.75)

HTTPS Configuration (NEW in v0.2.10):
- PANDA_ENABLE_HTTPS: Enable HTTPS for non-localhost access
- PANDA_HTTPS_PORT: HTTPS port (default: 7860)

All settings can be overridden via environment variables with PANDA_ prefix.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, AliasChoices
from pathlib import Path
from typing import Optional, List
import os


def get_default_base_dir() -> Path:
    """Return the default base directory for PANDA.1."""
    return Path.home() / ".panda1"


def get_env_file_path() -> Path:
    """Return the path to the .env file."""
    env_path = Path.home() / ".panda1" / ".env"
    if env_path.exists():
        return env_path
    # Fallback to current directory for development
    if Path(".env").exists():
        return Path(".env")
    return env_path  # Return default even if doesn't exist


class PandaConfig(BaseSettings):
    """
    PANDA.1 Configuration with sensible defaults.
    
    All paths default to ~/.panda1/ subdirectories.
    All settings can be overridden via PANDA_* environment variables.
    Configuration is loaded from ~/.panda1/.env by default.
    """
    
    # =========================================================================
    # OLLAMA / LLM CONFIGURATION
    # =========================================================================
    
    ollama_host: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices("PANDA_OLLAMA_HOST", "OLLAMA_BASE_URL"),
        description=(
            "Ollama server URL. Default is localhost for local usage. "
            "For remote access, Ollama must be configured to bind to 0.0.0.0. "
            "See docs/NETWORKING.md for details."
        )
    )

    ollama_embed_model: str = Field(
        default="nomic-embed-text",
        validation_alias=AliasChoices("PANDA_OLLAMA_EMBED_MODEL", "OLLAMA_EMBED_MODEL"),
        description="Embedding model to use with Ollama for vector memory."
    )
    
    llm_model: str = Field(
        default="panda1:latest",
        description=(
            "Default LLM model. Use 'panda1:latest' for the custom PANDA.1 model, "
            "or 'qwen2.5:7b-instruct-q4_K_M' as the base model fallback."
        )
    )
    
    llm_fallback_model: str = Field(
        default="qwen2.5:7b-instruct-q4_K_M",
        description="Fallback model if primary model is unavailable."
    )
    
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=4096, ge=128, le=8192)
    llm_context_length: int = Field(default=8192, ge=512, le=32768)
    
    # =========================================================================
    # OPENAI CLOUD LLM CONFIGURATION
    # =========================================================================
    
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for cloud LLM access"
    )
    
    openai_model: str = Field(
        default="gpt-4o",
        description="OpenAI model to use for research/latest info queries"
    )
    
    openai_web_search: bool = Field(
        default=True,
        description="Enable web search tool for OpenAI queries"
    )
    
    cloud_llm_enabled: bool = Field(
        default=True,
        description="Enable cloud LLM (OpenAI) for research/latest info"
    )
    
    cloud_timeout_seconds: int = Field(
        default=60,
        description="Timeout for cloud LLM requests"
    )
    
    # OpenAI Fallback (NEW in v0.2.10)
    openai_fallback_enabled: bool = Field(
        default=False,
        description="Enable GPT-4 fallback for low-confidence local responses"
    )
    
    openai_confidence_threshold: float = Field(
        default=0.75,
        description="Confidence threshold below which to use OpenAI fallback"
    )
    
    openai_max_output_tokens: int = Field(
        default=800,
        description="Maximum tokens for OpenAI fallback responses"
    )
    
    # =========================================================================
    # NETWORK / AGENT CONFIGURATION
    # =========================================================================
    
    # SCOTT News Agent (v0.2.10 - LAN HTTP)
    scott_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("PANDA_SCOTT_ENABLED", "SCOTT_ENABLED"),
        description="Enable SCOTT news integration"
    )
    scott_base_url: str = Field(
        default="http://192.168.1.18:8000",
        validation_alias=AliasChoices("PANDA_SCOTT_BASE_URL", "SCOTT_BASE_URL", "PANDA_SCOTT_API_URL", "SCOTT_API_URL"),
        description="SCOTT news agent base URL (LAN HTTP)"
    )
    scott_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("PANDA_SCOTT_API_KEY", "SCOTT_API_KEY"),
        description="SCOTT API key for authentication"
    )
    scott_timeout: int = Field(default=8, description="SCOTT request timeout in seconds")
    scott_retry_interval: int = Field(default=60, description="SCOTT retry interval in seconds")
    
    # Legacy alias for backwards compatibility
    @property
    def scott_api_url(self) -> str:
        """Return SCOTT API URL for backwards compatibility."""
        return f"{self.scott_base_url}/api"
    
    # PENNY Finance Agent
    penny_enabled: bool = Field(default=True, description="Enable PENNY finance integration")
    penny_api_url: str = Field(
        default="http://localhost:8003/api",
        description="PENNY finance agent API URL"
    )
    penny_timeout: int = Field(default=20, description="PENNY request timeout in seconds")
    
    # SENSEI Learning Hub
    sensei_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("PANDA_SENSEI_ENABLED", "SENSEI_ENABLED"),
        description="Enable SENSEI learning hub integration"
    )
    sensei_api_url: str = Field(
        default="http://192.168.1.19:5000",
        validation_alias=AliasChoices("PANDA_SENSEI_API_URL", "SENSEI_API_URL", "SENSEI_BASE_URL"),
        description="SENSEI learning hub base URL (LAN HTTP)"
    )
    sensei_timeout: int = Field(default=30, description="SENSEI request timeout in seconds")
    sensei_http_timeout_seconds: int = Field(
        default=10,
        validation_alias=AliasChoices("PANDA_SENSEI_HTTP_TIMEOUT_SECONDS", "SENSEI_HTTP_TIMEOUT_SECONDS"),
        description="SENSEI HTTP timeout for ping/download requests"
    )
    sensei_sync_interval_seconds: int = Field(
        default=600,
        validation_alias=AliasChoices("PANDA_SENSEI_SYNC_INTERVAL_SECONDS", "SENSEI_SYNC_INTERVAL_SECONDS"),
        description="SENSEI auto-sync interval (seconds)"
    )
    sensei_ping_interval_seconds: int = Field(
        default=10,
        validation_alias=AliasChoices("PANDA_SENSEI_PING_INTERVAL_SECONDS", "SENSEI_PING_INTERVAL_SECONDS"),
        description="SENSEI ping interval (seconds)"
    )
    sensei_max_download_mb: int = Field(
        default=50,
        validation_alias=AliasChoices("PANDA_SENSEI_MAX_DOWNLOAD_MB", "SENSEI_MAX_DOWNLOAD_MB"),
        description="Maximum SENSEI JSONL download size in MB"
    )

    # ECHO Context Hub (Database PC)
    echo_enabled: bool = Field(default=True, description="Enable ECHO context hub integration")
    echo_base_url: str = Field(
        default="http://192.168.1.20:9010",
        description="ECHO vector database base URL"
    )
    echo_api_key: str = Field(
        default="",
        description="ECHO API key for authentication"
    )
    echo_timeout: int = Field(default=8, description="ECHO request timeout in seconds")
    echo_top_k: int = Field(default=5, description="Default number of ECHO context results")
    
    # Local network info (for documentation/reference)
    panda_ip: str = Field(
        default="192.168.1.17",
        description="PANDA.1 machine IP address on local network"
    )
    
    # =========================================================================
    # VOICE CONFIGURATION (v0.2.10 - Faster-Whisper + Kokoro)
    # =========================================================================
    
    voice_enabled: bool = Field(default=True, description="Enable TTS voice output")
    
    # Speech-to-Text (STT) - Faster-Whisper (v0.2.10)
    stt_engine: str = Field(
        default="faster-whisper",
        description="STT engine: faster-whisper (default)"
    )
    
    stt_model: str = Field(
        default="small",
        description="Faster-Whisper model: tiny, base, small, medium, large-v3"
    )
    
    stt_compute_type: str = Field(
        default="int8",
        description="Faster-Whisper compute type: int8 (CPU), float16 (GPU)"
    )
    
    stt_device: str = Field(
        default="auto",
        description="STT device: auto, cpu, cuda"
    )
    
    # Text-to-Speech (TTS) - Kokoro (CPU) (v0.2.10)
    tts_engine: str = Field(
        default="kokoro",
        description="TTS engine: kokoro (CPU), null (off)"
    )

    tts_voice_en: str = Field(
        default="am_michael",
        description="English TTS voice (default: am_michael)"
    )

    tts_voice_ko: str = Field(
        default="am_michael",
        description="Korean TTS voice (default: am_michael)"
    )

    tts_speed: float = Field(
        default=1.0,
        description="TTS speech speed (0.5 - 2.0)"
    )

    tts_muted: bool = Field(
        default=False,
        description="Mute TTS output"
    )

    tts_device: str = Field(
        default="cpu",
        description="TTS device: cpu (default), cuda (if supported)"
    )
    
    tts_cache_dir: Optional[str] = Field(
        default=None,
        description="TTS model cache directory"
    )
    
    # Language mode (v0.2.10)
    language_mode: str = Field(
        default="auto",
        description="Voice language mode: auto (detect), en (English), ko (Korean)"
    )
    
    # PTT Settings (v0.2.10)
    ptt_enabled: bool = Field(
        default=True,
        description="Enable push-to-talk (Space bar)"
    )
    
    ptt_min_duration: float = Field(
        default=0.3,
        description="Minimum PTT recording duration (seconds)"
    )
    
    ptt_max_duration: float = Field(
        default=30.0,
        description="Maximum PTT recording duration (seconds)"
    )
    
    # Legacy settings (kept for backwards compatibility)
    whisper_model_wake: str = Field(
        default="tiny",
        description="[Deprecated] Use stt_model instead"
    )
    
    whisper_model_command: str = Field(
        default="base",
        description="[Deprecated] Use stt_model instead"
    )
    
    wake_phrases: str = Field(
        default="hey panda|yo panda",
        description="Wake phrases separated by |"
    )
    
    sleep_timeout_minutes: int = Field(
        default=5,
        description="Minutes of inactivity before returning to sleep mode"
    )
    
    # =========================================================================
    # AUDIO OUTPUT CONFIGURATION (v0.2.10)
    # =========================================================================
    
    alsa_device: str = Field(
        default="default",
        description="ALSA output device (use 'aplay -l' to list devices)"
    )
    
    audio_player: Optional[str] = Field(
        default=None,
        description="Custom audio player command (overrides auto-detection)"
    )
    
    audio_input_device: Optional[int] = Field(
        default=None,
        description="Audio input device index for microphone (None for system default)"
    )
    
    audio_output_device: Optional[int] = Field(
        default=None,
        description="Audio output device index (None for default)"
    )
    
    # =========================================================================
    # MEMORY SYSTEM
    # =========================================================================
    
    enable_memory: bool = Field(default=True)
    memory_collection: str = Field(default="panda1_memories")
    chromadb_telemetry: bool = Field(default=False)
    
    # =========================================================================
    # INTENT DETECTION
    # =========================================================================
    
    enable_intent_detection: bool = Field(default=True)
    intent_confidence_threshold: float = Field(
        default=0.65,
        description="Minimum confidence for intent matching"
    )
    
    # =========================================================================
    # WEB GUI SERVER (v0.2.10 - PTT + HTTPS)
    # =========================================================================
    
    gui_host: str = Field(
        default="0.0.0.0",
        description="GUI bind address (0.0.0.0 for LAN access, 127.0.0.1 for local only)"
    )
    gui_port: int = Field(
        default=7860,
        description="GUI HTTP port number"
    )
    gui_autostart: bool = Field(
        default=True,
        description="Auto-start GUI on PC boot"
    )
    gui_kiosk_mode: bool = Field(
        default=False,
        description="Launch browser in fullscreen kiosk mode"
    )
    
    # HTTPS Settings (v0.2.10)
    enable_https: bool = Field(
        default=True,
        description="Enable HTTPS (required for mic on non-localhost)"
    )
    https_port: int = Field(
        default=7860,
        description="HTTPS port number"
    )
    https_cert_dir: Optional[str] = Field(
        default=None,
        description="Directory for SSL certificates (default: ~/.panda1/certs)"
    )
    
    # GUI Voice Settings
    gui_voice_enabled: bool = Field(
        default=True,
        description="Enable voice assistant in GUI mode (PTT + TTS)"
    )
    
    voice_ack_enabled: bool = Field(
        default=True,
        description="Play TTS acknowledgment when ready"
    )
    
    # =========================================================================
    # API SERVER
    # =========================================================================
    
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_workers: int = Field(default=1)
    
    # =========================================================================
    # DIRECTORIES
    # =========================================================================
    
    base_dir: Path = Field(default_factory=get_default_base_dir)
    
    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"
    
    @property
    def memory_dir(self) -> Path:
        return self.base_dir / "memory"
    
    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "data" / "logs"
    
    @property
    def models_dir(self) -> Path:
        return self.base_dir / "models"
    
    @property
    def voices_cache_path(self) -> Path:
        return self.data_dir / "voices_cache.json"
    
    @property
    def gui_port_file(self) -> Path:
        return self.data_dir / "gui_port.json"
    
    @property
    def database_path(self) -> Path:
        return self.data_dir / "panda1.db"
    
    @property
    def audio_out_dir(self) -> Path:
        return self.base_dir / "audio_out"
    
    @property
    def audio_in_test_dir(self) -> Path:
        return self.base_dir / "audio_in_test"
    
    @property
    def certs_dir(self) -> Path:
        if self.https_cert_dir:
            return Path(self.https_cert_dir)
        return self.base_dir / "certs"
    
    @property
    def files_dir(self) -> Path:
        return self.base_dir / "files"
    
    @property
    def wake_phrase_list(self) -> List[str]:
        """Return wake phrases as a list."""
        return [p.strip().lower() for p in self.wake_phrases.split("|") if p.strip()]
    
    # =========================================================================
    # PYDANTIC CONFIG
    # =========================================================================
    
    model_config = {
        "env_prefix": "PANDA_",
        "env_file": str(get_env_file_path()),
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }
    
    @field_validator('ollama_host')
    @classmethod
    def validate_ollama_host(cls, v: str) -> str:
        """Ensure Ollama host has proper format."""
        if not v.startswith(('http://', 'https://')):
            v = f"http://{v}"
        return v.rstrip('/')

    @field_validator('sensei_api_url')
    @classmethod
    def validate_sensei_api_url(cls, v: str) -> str:
        """Ensure SENSEI base URL has proper format."""
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            v = f"http://{v}"
        v = v.rstrip('/')
        if v.endswith('/api'):
            v = v[:-4]
        return v

    @field_validator('scott_base_url')
    @classmethod
    def validate_scott_base_url(cls, v: str) -> str:
        """Ensure SCOTT base URL has proper format."""
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            v = f"http://{v}"
        v = v.rstrip('/')
        if v.endswith('/api'):
            v = v[:-4]
        return v
    
    @field_validator('language_mode')
    @classmethod
    def validate_language_mode(cls, v: str) -> str:
        """Ensure language mode is valid."""
        v = v.lower().strip()
        if v not in ('auto', 'en', 'ko'):
            return 'auto'
        return v
    
    def ensure_directories(self) -> None:
        """Create all required directories if they don't exist."""
        for dir_path in [
            self.data_dir, self.memory_dir, self.logs_dir, 
            self.models_dir, self.audio_out_dir, self.audio_in_test_dir,
            self.certs_dir, self.files_dir,
            self.base_dir / "cache" / "voice",
            self.base_dir / "cache" / "whisper",
            self.base_dir / "cache" / "kokoro",
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def get_ollama_url(self, endpoint: str = "") -> str:
        """
        Get full Ollama API URL for an endpoint.
        
        Args:
            endpoint: API endpoint (e.g., "/api/tags", "/api/chat")
        
        Returns:
            Full URL string
        """
        endpoint = endpoint.lstrip('/')
        if endpoint:
            return f"{self.ollama_host}/{endpoint}"
        return self.ollama_host
    
    def to_display_dict(self) -> dict:
        """Return config as dict for display (no sensitive data)."""
        return {
            "Version": "0.2.11",
            "Ollama Host": self.ollama_host,
            "LLM Model": self.llm_model,
            "Fallback Model": self.llm_fallback_model,
            "OpenAI Enabled": self.cloud_llm_enabled and bool(self.openai_api_key),
            "OpenAI Model": self.openai_model if self.cloud_llm_enabled else "disabled",
            "OpenAI Fallback": self.openai_fallback_enabled,
            "OpenAI Threshold": self.openai_confidence_threshold,
            "SCOTT Enabled": self.scott_enabled,
            "SCOTT URL": self.scott_base_url if self.scott_enabled else "disabled",
            "PENNY Enabled": self.penny_enabled,
            "PENNY URL": self.penny_api_url if self.penny_enabled else "disabled",
            "SENSEI Enabled": self.sensei_enabled,
            "SENSEI URL": self.sensei_api_url if self.sensei_enabled else "disabled",
            "ECHO Enabled": self.echo_enabled,
            "ECHO URL": self.echo_base_url if self.echo_enabled else "disabled",
            "Memory Enabled": self.enable_memory,
            "Voice Enabled": self.voice_enabled,
            "Language Mode": self.language_mode.upper(),
            "STT Engine": self.stt_engine,
            "STT Model": self.stt_model,
            "TTS Engine": self.tts_engine,
            "TTS Voice (EN)": self.tts_voice_en,
            "TTS Voice (KO)": self.tts_voice_ko,
            "TTS Device": self.tts_device,
            "TTS Muted": self.tts_muted,
            "PTT Enabled": self.ptt_enabled,
            "Audio Input Device": self.audio_input_device or "default",
            "Audio Output Device": self.audio_output_device or "default",
            "GUI Host": self.gui_host,
            "GUI Port": self.gui_port,
            "GUI Autostart": self.gui_autostart,
            "GUI Kiosk Mode": self.gui_kiosk_mode,
            "HTTPS Enabled": self.enable_https,
            "HTTPS Port": self.https_port if self.enable_https else "disabled",
            "GUI Voice Enabled": self.gui_voice_enabled,
            "Data Directory": str(self.base_dir),
        }


# Global config instance (singleton pattern)
_config: Optional[PandaConfig] = None


def get_config() -> PandaConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = PandaConfig()
        _config.ensure_directories()
    return _config


def reload_config() -> PandaConfig:
    """Force reload configuration from environment."""
    global _config
    _config = PandaConfig()
    _config.ensure_directories()
    return _config


# Convenience export
config = get_config()
