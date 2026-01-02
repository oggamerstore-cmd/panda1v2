"""
PANDA.1 SCOTT Client
====================
Client for communicating with SCOTT (Smart Curator Of Today's Topics) news agent.

Version: 0.2.11

Network Configuration:
- SCOTT runs on 192.168.1.18:8000
- Configure via PANDA_SCOTT_API_URL or PANDA_SCOTT_BASE_URL environment variable

Features:
- Health check with timeout handling
- Graceful offline handling
- Topic-based article filtering
- Article search functionality
"""

import logging
import time
from typing import List, Dict, Optional, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class ScottClient:
    """
    Client for SCOTT news agent API.
    
    SCOTT is a separate service running on the local network
    that curates and serves news articles.
    """
    
    def __init__(self, base_url: str, timeout: int = 10, max_retries: int = 3):
        """
        Initialize SCOTT client.

        Args:
            base_url: SCOTT API base URL (e.g., http://192.168.1.18:8000/api)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_error_time = 0
        self._consecutive_failures = 0
        self._throttle_interval = 60  # seconds to wait after 3 consecutive failures

        # Create session with retry strategy
        self._session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            connect=0,
            read=0,
            status=max_retries,
            other=0,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=frozenset(["GET"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._session.headers["User-Agent"] = "PANDA.1/0.2.11"

        logger.info(f"SCOTT client initialized: {self.base_url}")
    
    @property
    def is_throttled(self) -> bool:
        """Check if we should skip requests due to recent failures."""
        if self._consecutive_failures >= 3:
            elapsed = time.time() - self._last_error_time
            if elapsed < self._throttle_interval:
                return True
            # Reset after interval
            self._consecutive_failures = 0
        return False

    def _record_failure(self) -> None:
        """Record a failure for throttling."""
        self._consecutive_failures += 1
        self._last_error_time = time.time()

    def _record_success(self) -> None:
        """Record a success, resetting failure count."""
        self._consecutive_failures = 0

    def health_check(self) -> Dict[str, Any]:
        """
        Check SCOTT health status.

        Returns:
            Dict with health info
        """
        result = {
            "healthy": False,
            "url": self.base_url,
            "error": None
        }

        if self.is_throttled:
            result["error"] = f"SCOTT temporarily unavailable (retry in {self._throttle_interval}s)"
            return result

        try:
            response = self._session.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )

            if response.status_code == 200:
                result["healthy"] = True
                result["data"] = response.json()
                self._record_success()
            else:
                result["error"] = f"Status {response.status_code}"
                self._record_failure()

        except requests.exceptions.ConnectionError as e:
            result["error"] = f"Cannot connect to SCOTT at {self.base_url}"
            if "Connection refused" in str(e):
                result["error"] = f"Connection refused. Is SCOTT running at {self.base_url}?"
            logger.warning(f"SCOTT connection error: {self.base_url}/health")
            self._record_failure()
        except requests.exceptions.Timeout:
            result["error"] = f"Connection timeout ({self.timeout}s)"
            self._record_failure()
        except Exception as e:
            result["error"] = str(e)
            self._record_failure()

        return result
    
    def is_healthy(self) -> bool:
        """Quick health check - returns bool."""
        return self.health_check().get("healthy", False)
    
    def get_top_articles(
        self,
        limit: int = 5,
        topic: Optional[str] = None
    ) -> List[Dict]:
        """
        Get top news articles.

        Args:
            limit: Maximum articles to return
            topic: Filter by topic slug (optional)

        Returns:
            List of article dicts
        """
        if self.is_throttled:
            logger.debug("SCOTT throttled, skipping request")
            return []

        try:
            params = {"limit": limit}
            if topic:
                params["topic"] = topic

            response = self._session.get(
                f"{self.base_url}/articles/top",
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                self._record_success()
                data = response.json()
                return data.get("articles", data) if isinstance(data, dict) else data
            else:
                logger.warning(f"SCOTT returned status {response.status_code}")
                self._record_failure()
                return []

        except requests.exceptions.ConnectionError:
            logger.warning(f"SCOTT connection error: {self.base_url}/articles/top")
            self._record_failure()
            return []
        except requests.exceptions.Timeout:
            logger.warning(f"SCOTT timeout: {self.base_url}/articles/top")
            self._record_failure()
            return []
        except Exception as e:
            logger.error(f"SCOTT error: {e}")
            self._record_failure()
            return []
    
    def get_topics(self) -> List[Dict]:
        """
        Get available news topics.

        Returns:
            List of topic dicts with slug and name
        """
        if self.is_throttled:
            return []

        try:
            response = self._session.get(
                f"{self.base_url}/topics",
                timeout=self.timeout
            )

            if response.status_code == 200:
                self._record_success()
                data = response.json()
                return data.get("topics", data) if isinstance(data, dict) else data
            self._record_failure()
            return []

        except Exception as e:
            logger.error(f"Failed to get topics: {e}")
            self._record_failure()
            return []

    def get_articles_by_topic(
        self,
        topic: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get articles for a specific topic.

        Args:
            topic: Topic slug
            limit: Maximum articles

        Returns:
            List of article dicts
        """
        if self.is_throttled:
            return []

        try:
            response = self._session.get(
                f"{self.base_url}/articles/topic/{topic}",
                params={"limit": limit},
                timeout=self.timeout
            )

            if response.status_code == 200:
                self._record_success()
                data = response.json()
                return data.get("articles", data) if isinstance(data, dict) else data
            self._record_failure()
            return []

        except Exception as e:
            logger.error(f"Failed to get articles for topic {topic}: {e}")
            self._record_failure()
            return []

    def search_articles(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search articles by keyword.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching article dicts
        """
        if self.is_throttled:
            return []

        try:
            response = self._session.get(
                f"{self.base_url}/articles/search",
                params={"q": query, "limit": limit},
                timeout=self.timeout
            )

            if response.status_code == 200:
                self._record_success()
                data = response.json()
                return data.get("articles", data) if isinstance(data, dict) else data
            self._record_failure()
            return []

        except Exception as e:
            logger.error(f"Article search failed: {e}")
            self._record_failure()
            return []

    def get_status(self) -> Dict[str, Any]:
        """Get client status information."""
        return {
            "base_url": self.base_url,
            "timeout": self.timeout,
            "consecutive_failures": self._consecutive_failures,
            "is_throttled": self.is_throttled,
        }
