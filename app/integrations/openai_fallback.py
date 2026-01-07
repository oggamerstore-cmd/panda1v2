"""
PANDA.1 OpenAI Fallback Client
==============================
Confidence-gated GPT-4 fallback for low-confidence local responses.

Version: 2.0

Configuration:
- OPENAI_FALLBACK_ENABLED: Enable fallback (default: 0)
- OPENAI_API_KEY: Your OpenAI API key
- OPENAI_MODEL: Model to use (default: gpt-4.1)
- OPENAI_CONFIDENCE_THRESHOLD: Trigger threshold (default: 0.75)
- OPENAI_MAX_OUTPUT_TOKENS: Max response tokens (default: 800)

Features:
- Fast internet connectivity check
- Server-side API calls (key never exposed to frontend)
- Response labeling ("Verified via OpenAI")
"""

import os
import time
import socket
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None
    logger.info("openai not installed, fallback disabled")


@dataclass
class OpenAIConfig:
    """OpenAI fallback configuration."""
    enabled: bool = False
    api_key: str = ""
    model: str = "gpt-4.1"
    confidence_threshold: float = 0.75
    max_output_tokens: int = 800
    timeout: int = 30
    
    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        """Load configuration from environment variables."""
        return cls(
            enabled=os.environ.get("OPENAI_FALLBACK_ENABLED", "0") == "1",
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OPENAI_MODEL", "gpt-4.1"),
            confidence_threshold=float(os.environ.get("OPENAI_CONFIDENCE_THRESHOLD", "0.75")),
            max_output_tokens=int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "800")),
            timeout=int(os.environ.get("OPENAI_TIMEOUT", "30")),
        )
    
    @property
    def is_configured(self) -> bool:
        """Check if properly configured."""
        return self.enabled and bool(self.api_key)


@dataclass
class FallbackResult:
    """Result from OpenAI fallback."""
    success: bool
    response: str = ""
    model: str = ""
    tokens_used: int = 0
    response_time: float = 0.0
    error: Optional[str] = None
    used_fallback: bool = False


class OpenAIFallback:
    """
    OpenAI GPT-4 fallback for low-confidence responses.
    
    Usage:
        fallback = OpenAIFallback()
        
        # Check if fallback should be used
        if fallback.should_use_fallback(confidence=0.6):
            result = fallback.get_response(query, context)
    """
    
    # Internet connectivity test hosts
    CONNECTIVITY_HOSTS = [
        ("api.openai.com", 443),
        ("8.8.8.8", 53),
    ]
    
    def __init__(self, config: Optional[OpenAIConfig] = None):
        """
        Initialize OpenAI fallback.
        
        Args:
            config: OpenAI configuration (or loads from env)
        """
        self.config = config or OpenAIConfig.from_env()
        self._client: Optional[OpenAI] = None
        self._last_connectivity_check: float = 0
        self._is_connected: bool = False
    
    @property
    def is_available(self) -> bool:
        """Check if OpenAI fallback is available."""
        return OPENAI_AVAILABLE and self.config.is_configured
    
    def _get_client(self) -> Optional[OpenAI]:
        """Get or create OpenAI client."""
        if not OPENAI_AVAILABLE or not self.config.api_key:
            return None
        
        if self._client is None:
            self._client = OpenAI(
                api_key=self.config.api_key,
                timeout=self.config.timeout,
            )
        
        return self._client
    
    def check_connectivity(self, force: bool = False) -> bool:
        """
        Check internet connectivity.
        
        Args:
            force: Force check even if recently checked
        
        Returns:
            True if connected
        """
        # Cache connectivity check for 60 seconds
        now = time.time()
        if not force and (now - self._last_connectivity_check) < 60:
            return self._is_connected
        
        self._last_connectivity_check = now
        
        for host, port in self.CONNECTIVITY_HOSTS:
            try:
                sock = socket.create_connection((host, port), timeout=2)
                sock.close()
                self._is_connected = True
                return True
            except (socket.timeout, socket.error, OSError):
                continue
        
        self._is_connected = False
        return False
    
    def should_use_fallback(self, confidence: float) -> bool:
        """
        Determine if fallback should be used.
        
        Args:
            confidence: Local model confidence (0.0 - 1.0)
        
        Returns:
            True if fallback should be used
        """
        if not self.is_available:
            return False
        
        if confidence >= self.config.confidence_threshold:
            return False
        
        return self.check_connectivity()
    
    def get_response(
        self,
        query: str,
        context: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> FallbackResult:
        """
        Get response from OpenAI.
        
        Args:
            query: User query
            context: Optional context from conversation
            system_prompt: Optional custom system prompt
        
        Returns:
            FallbackResult with response
        """
        if not self.is_available:
            return FallbackResult(
                success=False,
                error="OpenAI fallback not available or not configured"
            )
        
        if not self.check_connectivity():
            return FallbackResult(
                success=False,
                error="No internet connection"
            )
        
        client = self._get_client()
        if not client:
            return FallbackResult(
                success=False,
                error="Failed to create OpenAI client"
            )
        
        start_time = time.time()
        
        try:
            # Build messages
            messages = []
            
            # System prompt
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            else:
                messages.append({
                    "role": "system",
                    "content": (
                        "You are PANDA.1, a helpful AI assistant for BOS. "
                        "Be concise, accurate, and helpful. "
                        "If you're uncertain about something, say so clearly."
                    )
                })
            
            # Context if provided
            if context:
                messages.append({
                    "role": "system",
                    "content": f"Conversation context:\n{context}"
                })
            
            # User query
            messages.append({"role": "user", "content": query})
            
            # Make API call
            response = client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                max_tokens=self.config.max_output_tokens,
                temperature=0.7,
            )
            
            response_time = time.time() - start_time
            
            # Extract response
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
            
            logger.info(
                f"OpenAI fallback used: {self.config.model}, "
                f"{tokens} tokens, {response_time:.2f}s"
            )
            
            return FallbackResult(
                success=True,
                response=content,
                model=self.config.model,
                tokens_used=tokens,
                response_time=response_time,
                used_fallback=True,
            )
            
        except Exception as e:
            logger.error(f"OpenAI fallback failed: {e}")
            return FallbackResult(
                success=False,
                error=str(e),
                response_time=time.time() - start_time,
            )
    
    def get_status(self) -> Dict[str, Any]:
        """Get fallback status."""
        return {
            "available": OPENAI_AVAILABLE,
            "enabled": self.config.enabled,
            "configured": self.config.is_configured,
            "model": self.config.model,
            "confidence_threshold": self.config.confidence_threshold,
            "connected": self._is_connected,
            "has_api_key": bool(self.config.api_key),
        }


# Global fallback instance
_fallback: Optional[OpenAIFallback] = None


def get_openai_fallback() -> OpenAIFallback:
    """Get or create the global OpenAI fallback."""
    global _fallback
    
    if _fallback is None:
        _fallback = OpenAIFallback()
    
    return _fallback


def check_openai_availability() -> Dict[str, Any]:
    """
    Check OpenAI fallback availability.
    
    Returns:
        Dict with availability status
    """
    fallback = get_openai_fallback()
    status = fallback.get_status()
    
    # Add connectivity check
    if status["configured"]:
        status["internet_available"] = fallback.check_connectivity(force=True)
    else:
        status["internet_available"] = False
    
    return status


def print_openai_doctor() -> None:
    """Print OpenAI fallback diagnostics to console."""
    logging.info(f"\n{'='*60}")
    logging.info("  PANDA.1 OpenAI Fallback Doctor")
    logging.info(f"{'='*60}")
    
    status = check_openai_availability()
    
    checks = [
        ("openai library", status["available"], "pip install openai"),
        ("OPENAI_FALLBACK_ENABLED", status["enabled"], "Set to 1 in .env"),
        ("OPENAI_API_KEY", status["has_api_key"], "Set in .env"),
        ("Internet connectivity", status.get("internet_available", False), "Check network"),
    ]
    
    for name, ok, fix in checks:
        icon = "✅" if ok else "❌"
        logging.info(f"\n  {icon} {name}")
        if not ok:
            logging.info(f"     Fix: {fix}")
    
    logging.info(f"\n  {'='*50}")
    
    if status["configured"] and status.get("internet_available"):
        logging.info("  ✅ OpenAI fallback ready")
        logging.info(f"     Model: {status['model']}")
        logging.info(f"     Threshold: {status['confidence_threshold']}")
    elif not status["enabled"]:
        logging.info("  ⏸️  OpenAI fallback disabled")
    else:
        logging.info("  ❌ OpenAI fallback not ready")
    
    logging.info()
