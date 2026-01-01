"""
PANDA.1 SCOTT Integration Client
=================================
Robust HTTP client for connecting to SCOTT news agent over LAN.

Version: 0.2.10

Network Configuration:
- PANDA.1 host: 192.168.1.17
- SCOTT host: 192.168.1.18:8000
- Uses X-API-Key authentication

Features:
- Connection pooling with retries
- Clear error messages for common failures
- Health check endpoint
- News topic fetching
- Search functionality
"""

import os
import time
import socket
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urljoin
import json

logger = logging.getLogger(__name__)

# Try to import requests
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("requests not available, SCOTT integration disabled")


@dataclass
class SCOTTConfig:
    """SCOTT connection configuration."""
    enabled: bool = True
    base_url: str = "http://192.168.1.18:8000"
    api_key: str = ""
    timeout: int = 8
    retry_count: int = 3
    retry_interval: int = 60
    
    @classmethod
    def from_env(cls) -> "SCOTTConfig":
        """Load configuration from environment variables."""
        # Support both PANDA_SCOTT_* (preferred) and legacy SCOTT_* env vars
        return cls(
            enabled=os.environ.get("PANDA_SCOTT_ENABLED", os.environ.get("SCOTT_ENABLED", "true")).lower() in ("1", "true", "yes"),
            base_url=os.environ.get("PANDA_SCOTT_BASE_URL", os.environ.get("SCOTT_BASE_URL", "http://192.168.1.18:8000")),
            api_key=os.environ.get("PANDA_SCOTT_API_KEY", os.environ.get("SCOTT_API_KEY", "")),
            timeout=int(os.environ.get("PANDA_SCOTT_TIMEOUT", os.environ.get("SCOTT_TIMEOUT_SEC", "8"))),
            retry_count=int(os.environ.get("PANDA_SCOTT_RETRY_COUNT", os.environ.get("SCOTT_RETRY_COUNT", "3"))),
            retry_interval=int(os.environ.get("PANDA_SCOTT_RETRY_INTERVAL", os.environ.get("SCOTT_RETRY_INTERVAL", "60"))),
        )


@dataclass
class SCOTTResponse:
    """Response from SCOTT API."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # timeout, connection, auth, not_found, server_error
    status_code: Optional[int] = None
    response_time: float = 0.0


class SCOTTClient:
    """
    HTTP client for SCOTT news agent.
    
    Usage:
        client = SCOTTClient()
        
        # Check health
        if client.health_check().success:
            # Get topics
            topics = client.get_topics()
            
            # Get top news
            news = client.get_top_news("korea", n=5)
    """
    
    def __init__(self, config: Optional[SCOTTConfig] = None):
        """
        Initialize SCOTT client.
        
        Args:
            config: SCOTT configuration (or loads from env)
        """
        self.config = config or SCOTTConfig.from_env()
        self._session: Optional[requests.Session] = None
        self._last_error_time: float = 0
        self._consecutive_failures: int = 0
    
    @property
    def is_available(self) -> bool:
        """Check if SCOTT client can be used."""
        return REQUESTS_AVAILABLE and self.config.enabled
    
    @property
    def is_throttled(self) -> bool:
        """Check if we should skip requests due to recent failures."""
        if self._consecutive_failures >= 3:
            elapsed = time.time() - self._last_error_time
            if elapsed < self.config.retry_interval:
                return True
            # Reset after interval
            self._consecutive_failures = 0
        return False
    
    def _get_session(self) -> requests.Session:
        """Get or create HTTP session with retry configuration."""
        if self._session is None:
            self._session = requests.Session()
            
            # Configure retries
            retry_strategy = Retry(
                total=self.config.retry_count,
                backoff_factor=0.5,
                status_forcelist=[500, 502, 503, 504],
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
            
            # Set default headers
            if self.config.api_key:
                self._session.headers["X-API-Key"] = self.config.api_key
            self._session.headers["Accept"] = "application/json"
            self._session.headers["User-Agent"] = "PANDA.1/0.2.10"
        
        return self._session
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> SCOTTResponse:
        """Make HTTP request to SCOTT."""
        if not REQUESTS_AVAILABLE:
            return SCOTTResponse(
                success=False,
                error="requests library not installed",
                error_type="dependency"
            )
        
        if not self.config.enabled:
            return SCOTTResponse(
                success=False,
                error="SCOTT integration disabled",
                error_type="disabled"
            )
        
        if self.is_throttled:
            return SCOTTResponse(
                success=False,
                error=f"SCOTT temporarily unavailable (retry in {self.config.retry_interval}s)",
                error_type="throttled"
            )
        
        url = urljoin(self.config.base_url, endpoint)
        start_time = time.time()
        
        try:
            session = self._get_session()
            
            response = session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.config.timeout,
            )
            
            response_time = time.time() - start_time
            
            # Handle response
            if response.status_code == 200:
                self._consecutive_failures = 0
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    data = {"text": response.text}
                
                return SCOTTResponse(
                    success=True,
                    data=data,
                    status_code=response.status_code,
                    response_time=response_time,
                )
            
            elif response.status_code == 401 or response.status_code == 403:
                return SCOTTResponse(
                    success=False,
                    error="Authentication failed. Check SCOTT_API_KEY.",
                    error_type="auth",
                    status_code=response.status_code,
                    response_time=response_time,
                )
            
            elif response.status_code == 404:
                return SCOTTResponse(
                    success=False,
                    error=f"Endpoint not found: {endpoint}",
                    error_type="not_found",
                    status_code=response.status_code,
                    response_time=response_time,
                )
            
            else:
                self._record_failure()
                return SCOTTResponse(
                    success=False,
                    error=f"Server error: {response.status_code}",
                    error_type="server_error",
                    status_code=response.status_code,
                    response_time=response_time,
                )
        
        except requests.exceptions.Timeout:
            self._record_failure()
            return SCOTTResponse(
                success=False,
                error=f"Request timeout ({self.config.timeout}s)",
                error_type="timeout",
                response_time=time.time() - start_time,
            )
        
        except requests.exceptions.ConnectionError as e:
            self._record_failure()
            error_msg = str(e)
            if "Connection refused" in error_msg:
                return SCOTTResponse(
                    success=False,
                    error=f"Connection refused. Is SCOTT running at {self.config.base_url}?",
                    error_type="connection",
                )
            elif "No route to host" in error_msg or "Network is unreachable" in error_msg:
                return SCOTTResponse(
                    success=False,
                    error=f"Network unreachable. Check LAN connection to SCOTT host.",
                    error_type="connection",
                )
            else:
                return SCOTTResponse(
                    success=False,
                    error=f"Connection error: {error_msg}",
                    error_type="connection",
                )
        
        except Exception as e:
            self._record_failure()
            logger.error(f"SCOTT request failed: {e}")
            return SCOTTResponse(
                success=False,
                error=str(e),
                error_type="unknown",
            )
    
    def _record_failure(self) -> None:
        """Record a failure for throttling."""
        self._consecutive_failures += 1
        self._last_error_time = time.time()
    
    def health_check(self) -> SCOTTResponse:
        """
        Check SCOTT server health.
        
        Returns:
            SCOTTResponse with health status
        """
        return self._make_request("GET", "/health")
    
    def get_topics(self) -> SCOTTResponse:
        """
        Get available news topics.
        
        Returns:
            SCOTTResponse with topics list
        """
        return self._make_request("GET", "/api/topics")
    
    def get_top_news(self, topic: str, n: int = 5) -> SCOTTResponse:
        """
        Get top news for a topic.
        
        Args:
            topic: News topic (korea, us, world, tech, mlb, etc.)
            n: Number of articles
        
        Returns:
            SCOTTResponse with news articles
        """
        return self._make_request("GET", f"/api/top/{topic}", params={"n": n})
    
    def search_news(self, query: str, topic: Optional[str] = None) -> SCOTTResponse:
        """
        Search news articles.
        
        Args:
            query: Search query
            topic: Optional topic filter
        
        Returns:
            SCOTTResponse with search results
        """
        params = {"q": query}
        if topic:
            params["topic"] = topic
        return self._make_request("GET", "/api/search", params=params)
    
    def get_daily_briefing(self, topics: Optional[List[str]] = None) -> SCOTTResponse:
        """
        Get daily news briefing.
        
        Args:
            topics: Optional list of topics (default: all)
        
        Returns:
            SCOTTResponse with briefing
        """
        params = {}
        if topics:
            params["topics"] = ",".join(topics)
        return self._make_request("GET", "/api/briefing", params=params)
    
    def get_status(self) -> Dict[str, Any]:
        """Get client status information."""
        return {
            "enabled": self.config.enabled,
            "base_url": self.config.base_url,
            "has_api_key": bool(self.config.api_key),
            "timeout": self.config.timeout,
            "consecutive_failures": self._consecutive_failures,
            "is_throttled": self.is_throttled,
            "requests_available": REQUESTS_AVAILABLE,
        }


# Global client instance
_scott_client: Optional[SCOTTClient] = None


def get_scott_client() -> SCOTTClient:
    """Get or create the global SCOTT client."""
    global _scott_client
    
    if _scott_client is None:
        _scott_client = SCOTTClient()
    
    return _scott_client


def scott_doctor() -> Dict[str, Any]:
    """
    Run SCOTT connection diagnostics.
    
    Returns:
        Dict with diagnostic results
    """
    results = {
        "overall": "unknown",
        "checks": [],
    }
    
    config = SCOTTConfig.from_env()
    
    # Check if enabled
    results["checks"].append({
        "name": "enabled",
        "status": "ok" if config.enabled else "warning",
        "message": f"SCOTT_ENABLED={config.enabled}"
    })
    
    # Check base URL
    results["checks"].append({
        "name": "base_url",
        "status": "ok",
        "message": f"SCOTT_BASE_URL={config.base_url}"
    })
    
    # Check API key
    if config.api_key:
        results["checks"].append({
            "name": "api_key",
            "status": "ok",
            "message": f"SCOTT_API_KEY=****{config.api_key[-4:]}" if len(config.api_key) > 4 else "SCOTT_API_KEY=***"
        })
    else:
        results["checks"].append({
            "name": "api_key",
            "status": "warning",
            "message": "SCOTT_API_KEY not set (may be required)"
        })
    
    if not config.enabled:
        results["overall"] = "disabled"
        return results
    
    # Parse host from base URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(config.base_url)
        host = parsed.hostname
        port = parsed.port or 8000
    except Exception:
        host = "192.168.1.18"
        port = 8000
    
    # TCP connectivity check
    try:
        sock = socket.create_connection((host, port), timeout=3)
        sock.close()
        results["checks"].append({
            "name": "tcp_connect",
            "status": "ok",
            "message": f"TCP connection to {host}:{port} successful"
        })
    except socket.timeout:
        results["checks"].append({
            "name": "tcp_connect",
            "status": "error",
            "message": f"TCP timeout connecting to {host}:{port}"
        })
        results["overall"] = "error"
        return results
    except ConnectionRefusedError:
        results["checks"].append({
            "name": "tcp_connect",
            "status": "error",
            "message": f"Connection refused at {host}:{port}. Is SCOTT running?"
        })
        results["overall"] = "error"
        return results
    except Exception as e:
        results["checks"].append({
            "name": "tcp_connect",
            "status": "error",
            "message": f"TCP error: {e}"
        })
        results["overall"] = "error"
        return results
    
    # HTTP health check
    client = SCOTTClient(config)
    health = client.health_check()
    
    if health.success:
        results["checks"].append({
            "name": "health_check",
            "status": "ok",
            "message": f"Health check OK ({health.response_time:.2f}s)"
        })
    else:
        results["checks"].append({
            "name": "health_check",
            "status": "error" if health.error_type in ("auth", "timeout", "connection") else "warning",
            "message": f"Health check failed: {health.error}"
        })
    
    # Topics endpoint check
    topics = client.get_topics()
    
    if topics.success:
        topic_count = len(topics.data.get("topics", [])) if topics.data else 0
        results["checks"].append({
            "name": "topics_api",
            "status": "ok",
            "message": f"Topics API OK ({topic_count} topics)"
        })
    else:
        results["checks"].append({
            "name": "topics_api",
            "status": "error" if topics.error_type == "auth" else "warning",
            "message": f"Topics API failed: {topics.error}"
        })
    
    # Determine overall status
    errors = [c for c in results["checks"] if c["status"] == "error"]
    warnings = [c for c in results["checks"] if c["status"] == "warning"]
    
    if errors:
        results["overall"] = "error"
    elif warnings:
        results["overall"] = "warning"
    else:
        results["overall"] = "ok"
    
    return results


def print_scott_doctor() -> None:
    """Print SCOTT diagnostics to console."""
    logging.info(f"\n{'='*60}")
    logging.info("  PANDA.1 SCOTT Doctor")
    logging.info(f"{'='*60}")
    
    results = scott_doctor()
    
    status_icons = {
        "ok": "✅",
        "warning": "⚠️",
        "error": "❌",
        "disabled": "⏸️",
    }
    
    for check in results["checks"]:
        icon = status_icons.get(check["status"], "?")
        logging.info(f"\n  {icon} {check['name']}")
        logging.info(f"     {check['message']}")
    
    logging.info(f"\n  {'='*50}")
    overall_icon = status_icons.get(results["overall"], "?")
    logging.info(f"  {overall_icon} Overall: {results['overall'].upper()}")
    
    if results["overall"] == "error":
        logging.info("\n  Common fixes:")
        logging.info("  • Ensure SCOTT is running: ssh scott 'pgrep -f uvicorn'")
        logging.info("  • Check firewall: sudo ufw allow from 192.168.1.17")
        logging.info("  • Verify API key matches on both servers")
    
    logging.info()
