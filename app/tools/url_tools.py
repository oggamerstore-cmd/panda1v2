"""
PANDA.1 URL Tools
=================
Safe URL generation for search and media services.

Version: 2.0

Features:
- YouTube search URL generation
- Spotify search URL generation
- Web search URL generation
- Safe URL validation
"""

import re
import logging
from urllib.parse import quote_plus, urlparse
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class URLResult:
    """Result of URL generation."""
    success: bool
    url: Optional[str] = None
    display_text: Optional[str] = None
    service: Optional[str] = None
    error: Optional[str] = None


# Allowed URL schemes and domains for opening
ALLOWED_SCHEMES = {"http", "https"}
ALLOWED_DOMAINS = {
    # Search engines
    "google.com", "www.google.com",
    "duckduckgo.com", "www.duckduckgo.com",
    "bing.com", "www.bing.com",
    # Video
    "youtube.com", "www.youtube.com", "youtu.be",
    # Music
    "spotify.com", "open.spotify.com",
    # News
    "news.google.com",
    # Reference
    "wikipedia.org", "en.wikipedia.org",
    # Weather
    "weather.com", "www.weather.com",
}


def youtube_search_url(query: str) -> URLResult:
    """
    Generate YouTube search URL.
    
    Args:
        query: Search query
    
    Returns:
        URLResult with YouTube search URL
    """
    if not query or not query.strip():
        return URLResult(
            success=False,
            error="Empty search query"
        )
    
    encoded_query = quote_plus(query.strip())
    url = f"https://www.youtube.com/results?search_query={encoded_query}"
    
    return URLResult(
        success=True,
        url=url,
        display_text=f"🎥 YouTube: {query}",
        service="youtube",
    )


def spotify_search_url(query: str, search_type: str = "track") -> URLResult:
    """
    Generate Spotify search URL.
    
    Args:
        query: Search query
        search_type: Type of search (track, artist, album, playlist)
    
    Returns:
        URLResult with Spotify search URL
    """
    if not query or not query.strip():
        return URLResult(
            success=False,
            error="Empty search query"
        )
    
    valid_types = {"track", "artist", "album", "playlist"}
    if search_type not in valid_types:
        search_type = "track"
    
    encoded_query = quote_plus(query.strip())
    url = f"https://open.spotify.com/search/{encoded_query}"
    
    icons = {
        "track": "🎵",
        "artist": "🎤",
        "album": "💿",
        "playlist": "📋",
    }
    icon = icons.get(search_type, "🎵")
    
    return URLResult(
        success=True,
        url=url,
        display_text=f"{icon} Spotify: {query}",
        service="spotify",
    )


def web_search_url(
    query: str,
    engine: str = "google"
) -> URLResult:
    """
    Generate web search URL.
    
    Args:
        query: Search query
        engine: Search engine (google, duckduckgo, bing)
    
    Returns:
        URLResult with search URL
    """
    if not query or not query.strip():
        return URLResult(
            success=False,
            error="Empty search query"
        )
    
    encoded_query = quote_plus(query.strip())
    
    engines = {
        "google": f"https://www.google.com/search?q={encoded_query}",
        "duckduckgo": f"https://duckduckgo.com/?q={encoded_query}",
        "bing": f"https://www.bing.com/search?q={encoded_query}",
    }
    
    engine = engine.lower()
    if engine not in engines:
        engine = "google"
    
    url = engines[engine]
    
    icons = {
        "google": "🔍",
        "duckduckgo": "🦆",
        "bing": "🔎",
    }
    icon = icons.get(engine, "🔍")
    
    return URLResult(
        success=True,
        url=url,
        display_text=f"{icon} Search: {query}",
        service=engine,
    )


def wikipedia_url(topic: str, lang: str = "en") -> URLResult:
    """
    Generate Wikipedia article URL.
    
    Args:
        topic: Article topic
        lang: Language code (en, ko, etc.)
    
    Returns:
        URLResult with Wikipedia URL
    """
    if not topic or not topic.strip():
        return URLResult(
            success=False,
            error="Empty topic"
        )
    
    # Wikipedia uses underscores for spaces
    formatted_topic = topic.strip().replace(" ", "_")
    encoded_topic = quote_plus(formatted_topic)
    
    url = f"https://{lang}.wikipedia.org/wiki/{encoded_topic}"
    
    return URLResult(
        success=True,
        url=url,
        display_text=f"📚 Wikipedia: {topic}",
        service="wikipedia",
    )


def weather_url(location: str) -> URLResult:
    """
    Generate weather search URL.
    
    Args:
        location: Location for weather
    
    Returns:
        URLResult with weather URL
    """
    if not location or not location.strip():
        return URLResult(
            success=False,
            error="Empty location"
        )
    
    encoded_location = quote_plus(location.strip())
    url = f"https://www.google.com/search?q=weather+{encoded_location}"
    
    return URLResult(
        success=True,
        url=url,
        display_text=f"🌤️ Weather: {location}",
        service="weather",
    )


def is_url_safe(url: str) -> bool:
    """
    Check if a URL is safe to open.
    
    Args:
        url: URL to check
    
    Returns:
        True if URL is safe
    """
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if parsed.scheme not in ALLOWED_SCHEMES:
            return False
        
        # Check domain
        domain = parsed.netloc.lower()
        
        # Remove port if present
        if ":" in domain:
            domain = domain.split(":")[0]
        
        # Check if domain or parent domain is allowed
        if domain in ALLOWED_DOMAINS:
            return True
        
        # Check if it's a subdomain of an allowed domain
        for allowed in ALLOWED_DOMAINS:
            if domain.endswith(f".{allowed}"):
                return True
        
        return False
        
    except Exception:
        return False


def open_url_safe(url: str) -> URLResult:
    """
    Validate and prepare a URL for safe opening.
    
    Args:
        url: URL to validate
    
    Returns:
        URLResult with validated URL
    """
    if not url or not url.strip():
        return URLResult(
            success=False,
            error="Empty URL"
        )
    
    url = url.strip()
    
    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    if is_url_safe(url):
        return URLResult(
            success=True,
            url=url,
            display_text=url,
            service="external",
        )
    else:
        return URLResult(
            success=False,
            error=f"URL not in allowed domains: {url}"
        )


def extract_urls(text: str) -> list:
    """
    Extract URLs from text.
    
    Args:
        text: Text to search
    
    Returns:
        List of found URLs
    """
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)


def format_clickable_link(url: str, text: Optional[str] = None) -> Dict[str, Any]:
    """
    Format a URL for clickable display in UI.
    
    Args:
        url: URL to format
        text: Display text (optional)
    
    Returns:
        Dict with link info for frontend
    """
    result = open_url_safe(url)
    
    if not result.success:
        return {
            "type": "text",
            "content": text or url,
            "error": result.error,
        }
    
    return {
        "type": "link",
        "url": result.url,
        "text": text or result.display_text,
        "safe": True,
        "target": "_blank",
    }
