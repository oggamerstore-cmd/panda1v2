"""
PANDA.1 SENSEI Client
=====================
Client for communicating with SENSEI (Smart Educational Network for
Systematic Enlightenment & Intelligence) learning hub.

Version: 2.0

Network Configuration:
- SENSEI runs on 192.168.0.120:5000
- Configure via SENSEI_BASE_URL or PANDA_SENSEI_API_URL

URL Structure:
- Health: /api/health or /health
- Knowledge injections: /api/knowledge_injections.jsonl

Features:
- Download lesson data from SENSEI
- Store learned content in PANDA's memory system
- Deep learning integration for knowledge acquisition
- Connection pooling with retry strategy
"""

import hashlib
import logging
import os
import time
from typing import List, Dict, Optional, Any, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import get_config

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
            base_url: SENSEI base URL (e.g., http://192.168.0.120:8002)
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
        self._knowledge_etag: Optional[str] = None
        self._knowledge_last_modified: Optional[str] = None

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
        self._session.headers["User-Agent"] = "PANDA.1/2.0"

        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

        self._public_session = requests.Session()
        self._public_session.mount("http://", adapter)
        self._public_session.mount("https://", adapter)
        self._public_session.headers["User-Agent"] = "PANDA.1/2.0"

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

    def ping(self) -> Tuple[bool, str]:
        """
        Ping SENSEI health endpoints.

        Tries /api/health then /health with no auth headers.

        Returns:
            Tuple of (connected, detail)
        """
        if self.is_throttled:
            return False, f"SENSEI temporarily unavailable (retry in {self._throttle_interval}s)"

        endpoints = ["/api/health", "/health"]
        timeout = self.timeout
        last_error = ""

        for endpoint in endpoints:
            url = f"{self.base_url}{endpoint}"
            try:
                response = self._public_session.get(url, timeout=timeout)
                if response.status_code == 200:
                    self._record_success()
                    logger.info("SENSEI ping success", extra={"endpoint": endpoint})
                    return True, f"ok ({endpoint})"
                last_error = f"Status {response.status_code} ({endpoint})"
                logger.warning("SENSEI ping failed", extra={"endpoint": endpoint, "status": response.status_code})
                self._record_failure()
            except requests.exceptions.Timeout:
                last_error = f"Timeout ({timeout}s) ({endpoint})"
                logger.warning("SENSEI ping timeout", extra={"endpoint": endpoint})
                self._record_failure()
            except requests.exceptions.ConnectionError:
                last_error = f"Cannot connect ({endpoint})"
                logger.warning("SENSEI ping connection error", extra={"endpoint": endpoint})
                self._record_failure()
            except Exception as exc:
                last_error = str(exc)
                logger.warning("SENSEI ping error", extra={"endpoint": endpoint, "error": str(exc)})
                self._record_failure()

        return False, last_error

    def download_knowledge_jsonl(self) -> Dict[str, Any]:
        """
        Download SENSEI knowledge_injections.jsonl with caching and size limits.

        Requires SENSEI to expose:
        GET /api/knowledge_injections.jsonl (FileResponse, no auth)

        Returns:
            Dict with downloaded status, metadata, and local_path.
        """
        config = get_config()
        cache_dir = config.base_dir / "cache" / "sensei"
        cache_dir.mkdir(parents=True, exist_ok=True)
        local_path = cache_dir / "knowledge_injections.jsonl"
        tmp_path = cache_dir / "knowledge_injections.jsonl.tmp"

        headers: Dict[str, str] = {}
        if self._knowledge_etag:
            headers["If-None-Match"] = self._knowledge_etag

        endpoints = ["/api/knowledge_injections.jsonl", "/knowledge_injections.jsonl"]
        max_bytes = int(config.sensei_max_download_mb) * 1024 * 1024
        backoffs = [0.5, 1.5]

        last_error = None
        api_404 = False

        for endpoint in endpoints:
            url = f"{self.base_url}{endpoint}"
            for attempt in range(len(backoffs) + 1):
                try:
                    logger.info("SENSEI download start", extra={"endpoint": endpoint, "attempt": attempt + 1})
                    response = self._public_session.get(
                        url,
                        headers=headers,
                        timeout=self.timeout,
                        stream=True,
                    )

                    if response.status_code == 404:
                        if endpoint.startswith("/api/"):
                            api_404 = True
                        last_error = f"Status 404 ({endpoint})"
                        logger.warning("SENSEI download 404", extra={"endpoint": endpoint})
                        break

                    if response.status_code == 304:
                        self._knowledge_etag = response.headers.get("ETag", self._knowledge_etag)
                        self._knowledge_last_modified = response.headers.get(
                            "Last-Modified",
                            self._knowledge_last_modified,
                        )
                        logger.info("SENSEI download not modified", extra={"endpoint": endpoint})
                        return {
                            "downloaded": False,
                            "bytes": 0,
                            "sha256": None,
                            "etag": self._knowledge_etag,
                            "last_modified": self._knowledge_last_modified,
                            "local_path": str(local_path),
                        }

                    if response.status_code >= 500:
                        last_error = f"Status {response.status_code} ({endpoint})"
                        logger.warning("SENSEI download server error", extra={"endpoint": endpoint, "status": response.status_code})
                        if attempt < len(backoffs):
                            time.sleep(backoffs[attempt])
                            continue
                        break

                    if response.status_code != 200:
                        last_error = f"Status {response.status_code} ({endpoint})"
                        logger.warning("SENSEI download failed", extra={"endpoint": endpoint, "status": response.status_code})
                        break

                    downloaded_bytes = 0
                    sha256 = hashlib.sha256()
                    with open(tmp_path, "wb") as handle:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if not chunk:
                                continue
                            downloaded_bytes += len(chunk)
                            if downloaded_bytes > max_bytes:
                                raise ValueError(
                                    f"SENSEI download exceeds {config.sensei_max_download_mb} MB limit"
                                )
                            sha256.update(chunk)
                            handle.write(chunk)

                    os.replace(tmp_path, local_path)

                    self._knowledge_etag = response.headers.get("ETag", self._knowledge_etag)
                    self._knowledge_last_modified = response.headers.get(
                        "Last-Modified",
                        self._knowledge_last_modified,
                    )

                    logger.info(
                        "SENSEI download complete",
                        extra={
                            "endpoint": endpoint,
                            "bytes": downloaded_bytes,
                            "etag": self._knowledge_etag,
                        },
                    )

                    return {
                        "downloaded": True,
                        "bytes": downloaded_bytes,
                        "sha256": sha256.hexdigest(),
                        "etag": self._knowledge_etag,
                        "last_modified": self._knowledge_last_modified,
                        "local_path": str(local_path),
                    }

                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                    last_error = str(exc)
                    logger.warning("SENSEI download transient error", extra={"endpoint": endpoint, "error": str(exc)})
                    if attempt < len(backoffs):
                        time.sleep(backoffs[attempt])
                        continue
                    break
                except Exception as exc:
                    last_error = str(exc)
                    logger.warning("SENSEI download failed", extra={"endpoint": endpoint, "error": str(exc)})
                    break
                finally:
                    if tmp_path.exists():
                        try:
                            tmp_path.unlink()
                        except Exception:
                            pass

            if last_error and endpoint != endpoints[-1]:
                continue

        if api_404:
            raise RuntimeError("SENSEI must expose GET /api/knowledge_injections.jsonl (FileResponse).")

        raise RuntimeError(last_error or "Failed to download SENSEI knowledge_injections.jsonl")

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

    if text_lower == "panda learn":
        return True
    if text_lower.startswith("panda learn "):
        return True
    if text_lower.startswith("panda, learn"):
        return True

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
