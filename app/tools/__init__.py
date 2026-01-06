"""
PANDA.1 Tools
=============
Safe tool implementations for documents, URLs, and search.

Version: 0.2.11

Tools:
- document: Open/preview .docx and text files
- urls: Generate safe YouTube/Spotify/web search URLs
"""

from .document_tool import (
    DocumentTool,
    DocumentResult,
    list_documents,
    open_document,
    summarize_document,
)

from .url_tools import (
    youtube_search_url,
    spotify_search_url,
    web_search_url,
    open_url_safe,
)

__all__ = [
    # Document
    "DocumentTool",
    "DocumentResult",
    "list_documents",
    "open_document",
    "summarize_document",
    # URLs
    "youtube_search_url",
    "spotify_search_url",
    "web_search_url",
    "open_url_safe",
]

__version__ = "0.2.11"
