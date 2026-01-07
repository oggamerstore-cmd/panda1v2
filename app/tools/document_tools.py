"""
PANDA.1 Document Tools
======================
Safe file browsing and document handling.

Version: 2.0

Features:
- Safe path resolution (no directory traversal)
- DOCX to HTML conversion
- Text file reading
- File summarization via LLM
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import python-docx
try:
    from docx import Document as DocxDocument
    from docx.shared import Inches
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.info("python-docx not available, DOCX support disabled")


@dataclass
class FileInfo:
    """File information."""
    name: str
    path: str
    relative_path: str
    size: int
    is_dir: bool
    extension: str
    modified: float


@dataclass
class DocumentContent:
    """Document content result."""
    success: bool
    content: str = ""
    html: str = ""
    file_type: str = ""
    word_count: int = 0
    error: Optional[str] = None


class DocumentTools:
    """
    Safe document handling tools.
    
    Usage:
        tools = DocumentTools()
        
        # List files
        files = tools.list_files("~/Documents")
        
        # Read document
        content = tools.read_document("~/Documents/report.docx")
    """
    
    # Allowed root directories
    ALLOWED_ROOTS = [
        Path.home() / "Documents",
        Path.home() / ".panda1" / "files",
    ]
    
    # Supported file types
    SUPPORTED_TYPES = {
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".json": "application/json",
        ".csv": "text/csv",
        ".log": "text/plain",
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    
    def __init__(self, extra_roots: Optional[List[Path]] = None):
        """
        Initialize document tools.
        
        Args:
            extra_roots: Additional allowed root directories
        """
        self.allowed_roots = list(self.ALLOWED_ROOTS)
        if extra_roots:
            self.allowed_roots.extend(extra_roots)
        
        # Ensure roots exist
        for root in self.allowed_roots:
            root.mkdir(parents=True, exist_ok=True)
    
    def _is_safe_path(self, path: Path) -> Tuple[bool, Optional[Path]]:
        """
        Check if path is safe (within allowed roots, no traversal).
        
        Args:
            path: Path to check
        
        Returns:
            Tuple of (is_safe, resolved_path)
        """
        try:
            # Resolve to absolute path
            resolved = path.expanduser().resolve()
            
            # Check against allowed roots
            for root in self.allowed_roots:
                root_resolved = root.resolve()
                try:
                    resolved.relative_to(root_resolved)
                    return True, resolved
                except ValueError:
                    continue
            
            return False, None
            
        except Exception as e:
            logger.warning(f"Path resolution error: {e}")
            return False, None
    
    def list_files(
        self,
        directory: str = "",
        extensions: Optional[List[str]] = None,
    ) -> List[FileInfo]:
        """
        List files in a directory.
        
        Args:
            directory: Directory path (relative to allowed roots or absolute)
            extensions: Filter by extensions (e.g., [".txt", ".docx"])
        
        Returns:
            List of FileInfo objects
        """
        files = []
        
        # If no directory specified, list allowed roots
        if not directory:
            for root in self.allowed_roots:
                if root.exists():
                    files.append(FileInfo(
                        name=root.name,
                        path=str(root),
                        relative_path=root.name,
                        size=0,
                        is_dir=True,
                        extension="",
                        modified=root.stat().st_mtime if root.exists() else 0,
                    ))
            return files
        
        # Resolve and validate path
        path = Path(directory)
        is_safe, resolved = self._is_safe_path(path)
        
        if not is_safe or not resolved or not resolved.exists():
            logger.warning(f"Invalid or unsafe path: {directory}")
            return []
        
        if not resolved.is_dir():
            logger.warning(f"Not a directory: {directory}")
            return []
        
        try:
            for item in sorted(resolved.iterdir()):
                # Skip hidden files
                if item.name.startswith("."):
                    continue
                
                ext = item.suffix.lower()
                
                # Filter by extension if specified
                if extensions and not item.is_dir():
                    if ext not in extensions:
                        continue
                
                # Only include supported types for files
                if not item.is_dir() and ext not in self.SUPPORTED_TYPES:
                    continue
                
                stat = item.stat()
                
                # Find relative path from nearest root
                rel_path = item.name
                for root in self.allowed_roots:
                    try:
                        rel_path = str(item.relative_to(root.resolve()))
                        break
                    except ValueError:
                        continue
                
                files.append(FileInfo(
                    name=item.name,
                    path=str(item),
                    relative_path=rel_path,
                    size=stat.st_size if item.is_file() else 0,
                    is_dir=item.is_dir(),
                    extension=ext,
                    modified=stat.st_mtime,
                ))
                
        except PermissionError:
            logger.warning(f"Permission denied: {directory}")
        except Exception as e:
            logger.error(f"Error listing files: {e}")
        
        return files
    
    def read_document(self, file_path: str) -> DocumentContent:
        """
        Read and parse a document.
        
        Args:
            file_path: Path to document
        
        Returns:
            DocumentContent with text and HTML
        """
        path = Path(file_path)
        is_safe, resolved = self._is_safe_path(path)
        
        if not is_safe or not resolved:
            return DocumentContent(
                success=False,
                error=f"Access denied: {file_path}"
            )
        
        if not resolved.exists():
            return DocumentContent(
                success=False,
                error=f"File not found: {file_path}"
            )
        
        if not resolved.is_file():
            return DocumentContent(
                success=False,
                error=f"Not a file: {file_path}"
            )
        
        # Check file size
        size = resolved.stat().st_size
        if size > self.MAX_FILE_SIZE:
            return DocumentContent(
                success=False,
                error=f"File too large: {size / 1024 / 1024:.1f} MB (max: {self.MAX_FILE_SIZE / 1024 / 1024:.0f} MB)"
            )
        
        ext = resolved.suffix.lower()
        
        if ext == ".docx":
            return self._read_docx(resolved)
        elif ext in (".txt", ".md", ".log", ".json", ".csv"):
            return self._read_text(resolved)
        else:
            return DocumentContent(
                success=False,
                error=f"Unsupported file type: {ext}"
            )
    
    def _read_text(self, path: Path) -> DocumentContent:
        """Read a text file."""
        try:
            content = path.read_text(encoding="utf-8")
            word_count = len(content.split())
            
            # Simple HTML conversion
            html = f"<pre>{self._escape_html(content)}</pre>"
            
            # Handle markdown
            if path.suffix.lower() == ".md":
                html = self._markdown_to_html(content)
            
            return DocumentContent(
                success=True,
                content=content,
                html=html,
                file_type=path.suffix.lower(),
                word_count=word_count,
            )
            
        except UnicodeDecodeError:
            return DocumentContent(
                success=False,
                error="File is not valid UTF-8 text"
            )
        except Exception as e:
            return DocumentContent(
                success=False,
                error=str(e)
            )
    
    def _read_docx(self, path: Path) -> DocumentContent:
        """Read a DOCX file."""
        if not DOCX_AVAILABLE:
            return DocumentContent(
                success=False,
                error="python-docx not installed. Run: pip install python-docx"
            )
        
        try:
            doc = DocxDocument(str(path))
            
            paragraphs = []
            html_parts = []
            
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
                    
                    # Determine HTML tag based on style
                    style_name = para.style.name.lower() if para.style else ""
                    
                    if "heading 1" in style_name:
                        html_parts.append(f"<h1>{self._escape_html(text)}</h1>")
                    elif "heading 2" in style_name:
                        html_parts.append(f"<h2>{self._escape_html(text)}</h2>")
                    elif "heading 3" in style_name:
                        html_parts.append(f"<h3>{self._escape_html(text)}</h3>")
                    else:
                        html_parts.append(f"<p>{self._escape_html(text)}</p>")
            
            content = "\n\n".join(paragraphs)
            html = "\n".join(html_parts)
            word_count = len(content.split())
            
            return DocumentContent(
                success=True,
                content=content,
                html=html,
                file_type=".docx",
                word_count=word_count,
            )
            
        except Exception as e:
            logger.error(f"Error reading DOCX: {e}")
            return DocumentContent(
                success=False,
                error=str(e)
            )
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        return (
            text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
    
    def _markdown_to_html(self, md: str) -> str:
        """Simple markdown to HTML conversion."""
        html = self._escape_html(md)
        
        # Headers
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        
        # Bold and italic
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
        
        # Code blocks
        html = re.sub(r'```(.+?)```', r'<pre><code>\1</code></pre>', html, flags=re.DOTALL)
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)
        
        # Lists
        html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', html)
        
        # Paragraphs
        lines = html.split('\n')
        for i, line in enumerate(lines):
            if line and not line.startswith('<'):
                lines[i] = f'<p>{line}</p>'
        html = '\n'.join(lines)
        
        return html


# URL tools
class URLTools:
    """
    Safe URL generation tools.
    
    Generates URLs for external services without exposing user data.
    """
    
    @staticmethod
    def youtube_search(query: str) -> str:
        """Generate YouTube search URL."""
        from urllib.parse import quote_plus
        return f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    
    @staticmethod
    def spotify_search(query: str, type: str = "track") -> str:
        """Generate Spotify search URL."""
        return f"https://open.spotify.com/search/{quote_plus(query)}"
    
    @staticmethod
    def google_search(query: str) -> str:
        """Generate Google search URL."""
        return f"https://www.google.com/search?q={quote_plus(query)}"
    
    @staticmethod
    def duckduckgo_search(query: str) -> str:
        """Generate DuckDuckGo search URL."""
        return f"https://duckduckgo.com/?q={quote_plus(query)}"
    
    @staticmethod
    def wikipedia_search(query: str) -> str:
        """Generate Wikipedia search URL."""
        return f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(query)}"
    
    @staticmethod
    def maps_search(query: str) -> str:
        """Generate Google Maps search URL."""
        return f"https://www.google.com/maps/search/{quote_plus(query)}"


# Global instances
_doc_tools: Optional[DocumentTools] = None


def get_document_tools() -> DocumentTools:
    """Get or create the global document tools."""
    global _doc_tools
    
    if _doc_tools is None:
        _doc_tools = DocumentTools()
    
    return _doc_tools
