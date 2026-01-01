"""
PANDA.1 Language Mode Manager
=============================
Handles language mode switching between English and Korean.

Version: 0.2.10

Supports:
- English commands: "Panda, speak Korean", "Panda, speak English"
- Korean commands: "판다, 한국어로 말해", "판다, 영어로 말해"

v0.2.10 Changes:
- Added set_mode() method alias for backward compatibility
"""

import re
import logging
from typing import Optional, Tuple, Literal

logger = logging.getLogger(__name__)

# Language mode type
LanguageMode = Literal["en", "ko"]


class LanguageModeManager:
    """
    Manages PANDA.1's output language mode.
    
    Detects language switch commands in user input and maintains
    the current language mode state.
    """
    
    # English switch patterns
    ENGLISH_SWITCH_PATTERNS = [
        # To Korean
        (r"\b(?:panda|hey panda|yo panda)[,\s]+speak\s+korean\b", "ko"),
        (r"\b(?:panda|hey panda|yo panda)[,\s]+switch\s+to\s+korean\b", "ko"),
        (r"\b(?:panda|hey panda|yo panda)[,\s]+respond\s+in\s+korean\b", "ko"),
        (r"\b(?:panda|hey panda|yo panda)[,\s]+korean\s+mode\b", "ko"),
        (r"\bspeak\s+(?:in\s+)?korean\b", "ko"),
        # To English
        (r"\b(?:panda|hey panda|yo panda)[,\s]+speak\s+english\b", "en"),
        (r"\b(?:panda|hey panda|yo panda)[,\s]+switch\s+to\s+english\b", "en"),
        (r"\b(?:panda|hey panda|yo panda)[,\s]+respond\s+in\s+english\b", "en"),
        (r"\b(?:panda|hey panda|yo panda)[,\s]+english\s+mode\b", "en"),
        (r"\bspeak\s+(?:in\s+)?english\b", "en"),
    ]
    
    # Korean switch patterns
    KOREAN_SWITCH_PATTERNS = [
        # To Korean
        (r"판다[,\s]*한국어로\s*말해", "ko"),
        (r"판다[,\s]*한국어\s*모드", "ko"),
        (r"판다[,\s]*한국말로\s*해", "ko"),
        (r"한국어로\s*(?:말해|대답해|응답해)", "ko"),
        # To English
        (r"판다[,\s]*영어로\s*말해", "en"),
        (r"판다[,\s]*영어\s*모드", "en"),
        (r"판다[,\s]*영어로\s*해", "en"),
        (r"영어로\s*(?:말해|대답해|응답해)", "en"),
    ]
    
    def __init__(self, initial_mode: LanguageMode = "en"):
        """
        Initialize the language mode manager.
        
        Args:
            initial_mode: Starting language mode ('en' or 'ko')
        """
        self._mode: LanguageMode = initial_mode
        self._compiled_english = [
            (re.compile(p, re.IGNORECASE), m) 
            for p, m in self.ENGLISH_SWITCH_PATTERNS
        ]
        self._compiled_korean = [
            (re.compile(p), m) 
            for p, m in self.KOREAN_SWITCH_PATTERNS
        ]
        logger.info(f"Language mode manager initialized: {self._mode}")
    
    @property
    def mode(self) -> LanguageMode:
        """Current language mode."""
        return self._mode
    
    @mode.setter
    def mode(self, value: LanguageMode) -> None:
        """Set the language mode."""
        if value in ("en", "ko"):
            old_mode = self._mode
            self._mode = value
            if old_mode != value:
                logger.info(f"Language mode changed: {old_mode} -> {value}")
    
    def set_mode(self, value: LanguageMode) -> None:
        """
        Set the language mode (method alias for property setter).
        
        This method provides backward compatibility for code that
        calls lang_mgr.set_mode() instead of using the property.
        
        Args:
            value: New language mode ('en' or 'ko')
        """
        self.mode = value
    
    @property
    def mode_name(self) -> str:
        """Human-readable mode name."""
        return "Korean" if self._mode == "ko" else "English"
    
    def detect_switch_command(self, text: str) -> Tuple[bool, Optional[LanguageMode]]:
        """
        Detect if the text contains a language switch command.
        
        Args:
            text: User input text
        
        Returns:
            Tuple of (is_switch_command, new_mode)
            If not a switch command, returns (False, None)
        """
        if not text:
            return False, None
        
        # Check English patterns
        for pattern, new_mode in self._compiled_english:
            if pattern.search(text):
                return True, new_mode
        
        # Check Korean patterns
        for pattern, new_mode in self._compiled_korean:
            if pattern.search(text):
                return True, new_mode
        
        return False, None
    
    def process_input(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Process user input and handle language switching.
        
        Args:
            text: User input text
        
        Returns:
            Tuple of (was_switch_command, acknowledgment_message)
            If it was a switch command, returns the acknowledgment.
            If not, returns (False, None).
        """
        is_switch, new_mode = self.detect_switch_command(text)
        
        if not is_switch or new_mode is None:
            return False, None
        
        old_mode = self._mode
        self._mode = new_mode
        
        # Generate acknowledgment in the NEW language
        if new_mode == "ko":
            if old_mode == "ko":
                msg = "네, 이미 한국어로 말하고 있어요, BOS."
            else:
                msg = "알겠습니다, BOS. 이제부터 한국어로 대답하겠습니다."
        else:  # English
            if old_mode == "en":
                msg = "Yes, I'm already speaking English, BOS."
            else:
                msg = "Got it, BOS. I'll respond in English from now on."
        
        logger.info(f"Language switched: {old_mode} -> {new_mode}")
        return True, msg
    
    def get_system_prompt_suffix(self) -> str:
        """
        Get the language instruction to append to system prompt.
        
        Returns:
            Language instruction string
        """
        if self._mode == "ko":
            return "\n\nIMPORTANT: You MUST respond in Korean (한국어). All your responses must be in Korean."
        else:
            return "\n\nIMPORTANT: You MUST respond in English. All your responses must be in English."
    
    def get_status(self) -> dict:
        """Get language mode status."""
        return {
            "mode": self._mode,
            "mode_name": self.mode_name,
        }


# Global instance
_language_manager: Optional[LanguageModeManager] = None


def get_language_manager() -> LanguageModeManager:
    """Get the global language mode manager."""
    global _language_manager
    if _language_manager is None:
        from config import get_config
        config = get_config()
        _language_manager = LanguageModeManager(initial_mode=config.language_mode)
    return _language_manager


def set_language_mode(mode: LanguageMode) -> None:
    """Set the global language mode."""
    get_language_manager().mode = mode


def get_language_mode() -> LanguageMode:
    """Get the current language mode."""
    return get_language_manager().mode


def process_language_command(text: str) -> Tuple[bool, Optional[str]]:
    """
    Process potential language switch command.
    
    Args:
        text: User input
    
    Returns:
        Tuple of (was_switch_command, acknowledgment)
    """
    return get_language_manager().process_input(text)
