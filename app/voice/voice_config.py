"""
PANDA.1 Voice Configuration
===========================
Persistent settings for voice subsystem.

Version: 0.2.10
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from enum import Enum

logger = logging.getLogger(__name__)


class LanguageMode(str, Enum):
    """Voice language mode."""
    AUTO = "auto"
    ENGLISH = "en"
    KOREAN = "ko"


class STTModel(str, Enum):
    """Faster-Whisper model sizes."""
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large-v3"


@dataclass
class VoiceConfig:
    """
    Voice subsystem configuration.
    
    Saved to ~/.panda1/voice_config.json
    """
    
    # Audio devices (None = system default)
    input_device: Optional[int] = None
    output_device: Optional[int] = None
    
    # Language settings
    language_mode: LanguageMode = LanguageMode.AUTO
    
    # STT settings
    stt_model: STTModel = STTModel.SMALL
    stt_compute_type: str = "int8"  # int8, float16, float32
    stt_beam_size: int = 5
    stt_vad_filter: bool = True
    
    # TTS settings
    tts_enabled: bool = True
    tts_speed: float = 1.0  # 0.5 - 2.0
    tts_volume: float = 1.0  # 0.0 - 1.0
    tts_muted: bool = False
    tts_voice_en: str = "en-US-EricNeural"  # English voice
    tts_voice_ko: str = "km_omega"  # Korean voice
    
    # PTT settings
    ptt_enabled: bool = True
    ptt_key: str = "space"  # Keyboard key for PTT
    ptt_min_duration: float = 0.3  # Minimum recording duration (seconds)
    ptt_max_duration: float = 30.0  # Maximum recording duration (seconds)
    ptt_silence_threshold: float = 0.01  # RMS threshold for silence detection
    
    # Audio settings
    sample_rate: int = 16000  # 16kHz for Whisper
    channels: int = 1  # Mono
    
    # Paths (set by get_voice_config)
    config_path: Optional[str] = None
    cache_dir: Optional[str] = None
    
    def save(self) -> bool:
        """Save configuration to file."""
        if not self.config_path:
            logger.warning("No config path set, cannot save")
            return False
        
        try:
            path = Path(self.config_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict, excluding paths
            data = asdict(self)
            data.pop("config_path", None)
            data.pop("cache_dir", None)
            
            # Convert enums to strings
            data["language_mode"] = self.language_mode.value
            data["stt_model"] = self.stt_model.value
            
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Voice config saved to {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save voice config: {e}")
            return False
    
    @classmethod
    def load(cls, path: Path) -> "VoiceConfig":
        """Load configuration from file."""
        config = cls()
        config.config_path = str(path)
        
        if path.exists():
            try:
                with open(path) as f:
                    data = json.load(f)
                
                # Handle enums
                if "language_mode" in data:
                    data["language_mode"] = LanguageMode(data["language_mode"])
                if "stt_model" in data:
                    data["stt_model"] = STTModel(data["stt_model"])
                
                # Update config with loaded values
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                
                logger.info(f"Voice config loaded from {path}")
                
            except Exception as e:
                logger.warning(f"Failed to load voice config: {e}, using defaults")
        
        return config
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "input_device": self.input_device,
            "output_device": self.output_device,
            "language_mode": self.language_mode.value,
            "stt_model": self.stt_model.value,
            "stt_compute_type": self.stt_compute_type,
            "tts_enabled": self.tts_enabled,
            "tts_speed": self.tts_speed,
            "tts_volume": self.tts_volume,
            "tts_muted": self.tts_muted,
            "tts_voice_en": self.tts_voice_en,
            "tts_voice_ko": self.tts_voice_ko,
            "ptt_enabled": self.ptt_enabled,
            "ptt_key": self.ptt_key,
            "sample_rate": self.sample_rate,
        }


# Global config instance
_voice_config: Optional[VoiceConfig] = None


def get_voice_config(panda_home: Optional[Path] = None) -> VoiceConfig:
    """
    Get or create the global voice configuration.
    
    Args:
        panda_home: PANDA.1 home directory (default: ~/.panda1)
    
    Returns:
        VoiceConfig instance
    """
    global _voice_config
    
    if _voice_config is None:
        if panda_home is None:
            panda_home = Path.home() / ".panda1"
        
        config_path = panda_home / "voice_config.json"
        cache_dir = panda_home / "cache" / "voice"
        
        _voice_config = VoiceConfig.load(config_path)
        _voice_config.config_path = str(config_path)
        _voice_config.cache_dir = str(cache_dir)
        
        # Ensure cache directory exists
        cache_dir.mkdir(parents=True, exist_ok=True)
    
    return _voice_config


def reset_voice_config() -> None:
    """Reset the global voice configuration."""
    global _voice_config
    _voice_config = None
