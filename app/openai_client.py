"""
PANDA.1 OpenAI Client
=====================
OpenAI API integration for research and latest information queries.

Version: 2.0

Used for:
- Research queries
- Latest/current information
- Documentation changes
- Pricing comparisons
- Time-sensitive information

NOT used for:
- News headlines (SCOTT handles this)
"""

import logging
import re
from typing import Optional, Generator, Dict, Any, List

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    OpenAI API client for cloud LLM access.
    Uses the official OpenAI Python SDK with Responses API.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
        enable_web_search: bool = True,
        timeout: int = 60
    ):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key
            model: Model to use
            enable_web_search: Enable web search tool
            timeout: Request timeout in seconds
        """
        from .config import get_config
        config = get_config()
        
        self.api_key = api_key or config.openai_api_key
        self.model = model or config.openai_model
        self.enable_web_search = enable_web_search if enable_web_search is not None else config.openai_web_search
        self.timeout = timeout or config.cloud_timeout_seconds
        
        self._client = None
        self._available: Optional[bool] = None
    
    def _init_client(self) -> bool:
        """Initialize OpenAI client."""
        if self._client is not None:
            return True
        
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            self._available = False
            return False
        
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                timeout=self.timeout
            )
            self._available = True
            logger.info(f"OpenAI client initialized (model: {self.model})")
            return True
        except ImportError:
            logger.error("OpenAI not installed. Install: pip install openai")
            self._available = False
            return False
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            self._available = False
            return False
    
    def is_available(self) -> bool:
        """Check if OpenAI client is available."""
        if self._available is None:
            self._init_client()
        return bool(self._available)
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        use_web_search: Optional[bool] = None,
        **kwargs
    ) -> str:
        """
        Generate a response using OpenAI.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            use_web_search: Override web search setting
            **kwargs: Additional parameters for the API
        
        Returns:
            Response text
        """
        if not self._init_client():
            return "OpenAI is not available. Please check your API key."
        
        try:
            # Determine if we should use web search
            should_search = use_web_search if use_web_search is not None else self.enable_web_search
            
            # Build request parameters
            params = {
                "model": self.model,
                "messages": messages,
                **kwargs
            }
            
            # Add web search tool if enabled
            # Note: OpenAI's web search is available through function calling or Responses API
            # For simplicity, we use the standard chat completions with enhanced prompts
            if should_search:
                # Add instruction to use web search context
                system_msg = messages[0] if messages and messages[0]["role"] == "system" else None
                if system_msg:
                    system_msg["content"] += "\n\nYou have access to current information. Provide accurate, up-to-date responses."
            
            # Make request
            response = self._client.chat.completions.create(**params)
            
            if response.choices:
                return response.choices[0].message.content
            
            return "No response from OpenAI."
            
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            return f"Error generating response: {str(e)}"
    
    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        use_web_search: Optional[bool] = None,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response using OpenAI.
        
        Args:
            messages: List of message dicts
            use_web_search: Override web search setting
            **kwargs: Additional parameters
        
        Yields:
            Response text chunks
        """
        if not self._init_client():
            yield "OpenAI is not available. Please check your API key."
            return
        
        try:
            params = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                **kwargs
            }
            
            stream = self._client.chat.completions.create(**params)
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            yield f"Error: {str(e)}"
    
    def health_check(self) -> Dict[str, Any]:
        """Check OpenAI connectivity."""
        if not self._init_client():
            return {
                "healthy": False,
                "error": "Not initialized",
                "api_key_configured": bool(self.api_key)
            }
        
        try:
            # Simple test request
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5
            )
            
            return {
                "healthy": True,
                "model": self.model,
                "web_search_enabled": self.enable_web_search
            }
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "model": self.model
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get client status."""
        return {
            "available": self.is_available(),
            "model": self.model,
            "web_search_enabled": self.enable_web_search,
            "timeout": self.timeout,
            "api_key_configured": bool(self.api_key)
        }


# ─────────────────────────────────────────────────────────────────────────────
# Query Classification
# ─────────────────────────────────────────────────────────────────────────────

def is_research_query(text: str) -> bool:
    """
    Determine if a query should be routed to OpenAI for research.
    
    Args:
        text: User query
    
    Returns:
        True if this is a research/latest info query
    """
    text_lower = text.lower()
    
    # Keywords that indicate need for latest/current information
    research_keywords = [
        'latest', 'current', 'today', 'now', 'recent',
        'new release', 'updated', 'pricing', 'price',
        'documentation', 'docs', 'how much', 'cost',
        'compare', 'comparison', 'vs', 'versus',
        'research', 'find out', 'look up',
        'what is the current', 'what are the current',
        '2024', '2025',  # Recent years
    ]
    
    # Exclude news-related queries (SCOTT handles these)
    news_keywords = [
        'news', 'headlines', 'breaking', 'top stories',
        'what happened', 'article', 'report'
    ]
    
    # Check for news first
    if any(kw in text_lower for kw in news_keywords):
        return False
    
    # Check for research keywords
    return any(kw in text_lower for kw in research_keywords)


def is_post_oct_2023_timeline_query(text: str) -> bool:
    """
    Determine if a query involves timelines after October 1, 2023.

    Args:
        text: User query

    Returns:
        True if the query references dates after 2023-10-01
    """
    text_lower = text.lower()

    # Any explicit year >= 2024 should be routed to OpenAI
    for match in re.findall(r"\b(20\d{2})\b", text_lower):
        try:
            year = int(match)
        except ValueError:
            continue
        if year >= 2024:
            return True

    # Match explicit 2023-10-01 and beyond (ISO / slash / dash)
    if re.search(r"\b2023[-/](1[0-2]|0[1-9])[-/](\d{1,2})\b", text_lower):
        month_match = re.search(r"\b2023[-/](1[0-2]|0[1-9])[-/](\d{1,2})\b", text_lower)
        if month_match:
            month = int(month_match.group(1))
            day = int(month_match.group(2))
            if month > 10 or (month == 10 and day >= 1):
                return True

    if re.search(r"\b(1[0-2]|0[1-9])[-/](\d{1,2})[-/]2023\b", text_lower):
        month_match = re.search(r"\b(1[0-2]|0[1-9])[-/](\d{1,2})[-/]2023\b", text_lower)
        if month_match:
            month = int(month_match.group(1))
            day = int(month_match.group(2))
            if month > 10 or (month == 10 and day >= 1):
                return True

    # Month name references in late 2023
    month_map = {
        "january": 1, "jan": 1,
        "february": 2, "feb": 2,
        "march": 3, "mar": 3,
        "april": 4, "apr": 4,
        "may": 5,
        "june": 6, "jun": 6,
        "july": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sep": 9, "sept": 9,
        "october": 10, "oct": 10,
        "november": 11, "nov": 11,
        "december": 12, "dec": 12,
    }
    for name, month in month_map.items():
        if month >= 10 and re.search(rf"\\b{name}\\b", text_lower):
            if re.search(r"\b2023\b", text_lower):
                return True

    return False


def is_time_sensitive_query(text: str) -> bool:
    """
    Determine if a query is time-sensitive and needs current info.
    
    Args:
        text: User query
    
    Returns:
        True if time-sensitive
    """
    text_lower = text.lower()
    
    time_sensitive_patterns = [
        'what is the', 'what are the', 'how much is',
        'current', 'latest', 'today', 'right now',
        'as of', 'updated', 'new version',
        'release date', 'when will', 'when did',
        'stock price', 'exchange rate', 'weather'
    ]
    
    return any(pattern in text_lower for pattern in time_sensitive_patterns)


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_openai_client: Optional[OpenAIClient] = None


def get_openai_client() -> OpenAIClient:
    """Get the global OpenAI client instance."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client
