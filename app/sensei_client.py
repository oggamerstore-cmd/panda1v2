"""
PANDA.1 SENSEI Client
=====================
Client for communicating with SENSEI (Smart Educational Network for
Systematic Enlightenment & Intelligence) learning hub.

Version: 0.2.12

Network Configuration:
- SENSEI runs on 192.168.1.19:8002
- Configure via PANDA_SENSEI_API_URL environment variable

URL Structure:
- Health: /health (no /api prefix)
- Lessons: /api/lessons
- Knowledge: /api/knowledge/download

Features:
- Download lesson data from SENSEI
- Store learned content in PANDA's memory system
- Deep learning integration for knowledge acquisition
- Connection pooling with retry strategy
"""

import logging
import time
from typing import List, Dict, Optional, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SenseiClient:
    """
    Client for SENSEI learning hub API.

    SENSEI is a separate service running on the local network
    that collects and serves educational content/lessons.
    """

    def __init__(self, base_url: str, timeout: int = 15, api_key: str = "", max_retries: int = 3):
        """
        Initialize SENSEI client.

        Args:
            base_url: SENSEI base URL (e.g., http://192.168.1.19:8002)
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
            max_retries: Maximum retry attempts for failed requests
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.api_key = api_key
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
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._session.headers["User-Agent"] = "PANDA.1/0.2.12"

        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

        logger.info(f"SENSEI client initialized: {self.base_url}")

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

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def health_check(self) -> Dict[str, Any]:
        """
        Check SENSEI health status.

        Returns:
            Dict with health info
        """
        result = {
            "healthy": False,
            "url": self.base_url,
            "error": None
        }

        if self.is_throttled:
            result["error"] = f"SENSEI temporarily unavailable (retry in {self._throttle_interval}s)"
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
            result["error"] = f"Cannot connect to SENSEI at {self.base_url}"
            if "Connection refused" in str(e):
                result["error"] = f"Connection refused. Is SENSEI running at {self.base_url}?"
            logger.warning(f"SENSEI connection error: {self.base_url}/health")
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

    def get_lessons(self, limit: int = 50, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Get available lessons from SENSEI.

        Args:
            limit: Maximum lessons to return
            category: Filter by category (optional)

        Returns:
            Dict with lessons data and metadata
        """
        result = {
            "success": False,
            "lessons": [],
            "count": 0,
            "error": None
        }

        if self.is_throttled:
            result["error"] = f"SENSEI temporarily unavailable (retry in {self._throttle_interval}s)"
            return result

        try:
            params = {"limit": limit}
            if category:
                params["category"] = category

            response = self._session.get(
                f"{self.base_url}/api/lessons",
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                result["success"] = True
                result["lessons"] = data.get("lessons", [])
                result["count"] = len(result["lessons"])
                self._record_success()
            else:
                result["error"] = f"Status {response.status_code}"
                self._record_failure()

        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to SENSEI"
            logger.error(f"SENSEI connection error: {self.base_url}/api/lessons")
            self._record_failure()
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout"
            self._record_failure()
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"SENSEI error: {e}")
            self._record_failure()

        return result

    def get_lesson_content(self, lesson_id: str) -> Dict[str, Any]:
        """
        Get detailed content for a specific lesson.

        Args:
            lesson_id: The lesson ID to fetch

        Returns:
            Dict with lesson content
        """
        result = {
            "success": False,
            "lesson": None,
            "error": None
        }

        if self.is_throttled:
            result["error"] = f"SENSEI temporarily unavailable (retry in {self._throttle_interval}s)"
            return result

        try:
            response = self._session.get(
                f"{self.base_url}/api/lessons/{lesson_id}",
                timeout=self.timeout
            )

            if response.status_code == 200:
                result["success"] = True
                result["lesson"] = response.json()
                self._record_success()
            elif response.status_code == 404:
                result["error"] = f"Lesson {lesson_id} not found"
            else:
                result["error"] = f"Status {response.status_code}"
                self._record_failure()

        except requests.exceptions.ConnectionError:
            result["error"] = "Cannot connect to SENSEI"
            self._record_failure()
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout"
            self._record_failure()
        except Exception as e:
            result["error"] = str(e)
            self._record_failure()

        return result

    def download_knowledge(self, topic: Optional[str] = None) -> Dict[str, Any]:
        """
        Download all lesson knowledge for a topic (deep learning).

        This is the main method for "learn from sensei" command.
        Downloads structured knowledge that can be stored in memory.

        Args:
            topic: Optional topic filter (e.g., "business", "tech", "korean")

        Returns:
            Dict with knowledge items ready for memory storage
        """
        result = {
            "success": False,
            "knowledge": [],
            "count": 0,
            "topic": topic or "all",
            "error": None
        }

        if self.is_throttled:
            result["error"] = f"SENSEI temporarily unavailable (retry in {self._throttle_interval}s)"
            return result

        try:
            params = {}
            if topic:
                params["topic"] = topic

            # Use longer timeout for knowledge download (may have lots of data)
            download_timeout = max(self.timeout, 60)
            response = self._session.get(
                f"{self.base_url}/api/knowledge/download",
                params=params,
                timeout=download_timeout
            )

            if response.status_code == 200:
                data = response.json()
                result["success"] = True
                result["knowledge"] = data.get("knowledge", data.get("items", []))
                result["count"] = len(result["knowledge"])
                result["source"] = "sensei"
                logger.info(f"Downloaded {result['count']} knowledge items from SENSEI")
                self._record_success()
            else:
                result["error"] = f"Status {response.status_code}"
                self._record_failure()

        except requests.exceptions.ConnectionError as e:
            result["error"] = "Cannot connect to SENSEI"
            if "Connection refused" in str(e):
                result["error"] = f"Connection refused. Is SENSEI running at {self.base_url}?"
            logger.error(f"SENSEI connection error during knowledge download")
            self._record_failure()
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout - SENSEI may have a lot of data"
            self._record_failure()
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"SENSEI knowledge download error: {e}")
            self._record_failure()

        return result

    def get_categories(self) -> List[str]:
        """
        Get available lesson categories.

        Returns:
            List of category names
        """
        if self.is_throttled:
            return []

        try:
            response = self._session.get(
                f"{self.base_url}/api/categories",
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                self._record_success()
                return data.get("categories", [])
            self._record_failure()
            return []

        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            self._record_failure()
            return []

    def submit_feedback(self, lesson_id: str, rating: int, notes: str = "") -> bool:
        """
        Submit feedback on a lesson (for SENSEI to improve).

        Args:
            lesson_id: The lesson ID
            rating: Rating 1-5
            notes: Optional feedback notes

        Returns:
            True if feedback was submitted successfully
        """
        if self.is_throttled:
            return False

        try:
            response = self._session.post(
                f"{self.base_url}/api/feedback",
                json={
                    "lesson_id": lesson_id,
                    "rating": rating,
                    "notes": notes,
                    "source": "panda1"
                },
                timeout=self.timeout
            )

            if response.status_code in (200, 201):
                self._record_success()
                return True
            self._record_failure()
            return False

        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            self._record_failure()
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get client status information."""
        return {
            "base_url": self.base_url,
            "timeout": self.timeout,
            "consecutive_failures": self._consecutive_failures,
            "is_throttled": self.is_throttled,
        }


def is_learning_command(text: str) -> bool:
    """
    Check if text is a learning/SENSEI command.

    Args:
        text: User input text

    Returns:
        True if this is a learning command
    """
    text_lower = text.lower().strip()

    learning_patterns = [
        # Primary commands
        "panda learn",
        "panda, learn",
        "learn panda",
        "learn from sensei",
        "sensei learn",
        # Alternative phrasings
        "download lessons",
        "get lessons from sensei",
        "get lessons",
        "sensei teach",
        "teach me sensei",
        "update knowledge from sensei",
        "update knowledge",
        "sync with sensei",
        "sync sensei",
        "deep learn",
        "acquire knowledge",
        # Natural language
        "time to learn",
        "start learning",
        "learn something new",
        "what can sensei teach",
        "connect to sensei",
        "download from sensei",
    ]

    return any(pattern in text_lower for pattern in learning_patterns)
