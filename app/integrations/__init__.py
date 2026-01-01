"""
PANDA.1 Integrations
====================
External service integrations for PANDA.1.

Version: 0.2.11

Integrations:
- SCOTT: News agent (LAN HTTP API)
- OpenAI: GPT-4 fallback (cloud API)
"""

from .scott_client import (
    SCOTTClient,
    SCOTTConfig,
    SCOTTResponse,
    get_scott_client,
    scott_doctor,
    print_scott_doctor,
)

from .openai_fallback import (
    OpenAIFallback,
    OpenAIConfig,
    FallbackResult,
    get_openai_fallback,
    check_openai_availability,
    print_openai_doctor,
)

__all__ = [
    # SCOTT
    "SCOTTClient",
    "SCOTTConfig", 
    "SCOTTResponse",
    "get_scott_client",
    "scott_doctor",
    "print_scott_doctor",
    # OpenAI
    "OpenAIFallback",
    "OpenAIConfig",
    "FallbackResult",
    "get_openai_fallback",
    "check_openai_availability",
    "print_openai_doctor",
]

__version__ = "0.2.10"
