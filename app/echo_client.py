"""
PANDA.1 ECHO Client
===================
Client for communicating with ECHO (External Context Hub Orchestrator).

Version: 0.2.11

Network Configuration:
- ECHO runs on a dedicated Database PC (default: http://192.168.1.20:9010)
- Configure via PANDA_ECHO_BASE_URL and PANDA_ECHO_API_KEY

Features:
- Health check with timeout handling
- Query for top-k context snippets
- Graceful offline handling with throttling
"""

import logging
import time
from typing import Dict, List, Optional, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class EchoClient:
    """Client for ECHO context service."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 8,
        api_key: Optional[str] = None,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = api_key
        self.max_retries = max_retries
        self._last_error_time = 0
        self._consecutive_failures = 0
        self._throttle_interval = 30

        self._session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.4,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._session.headers["User-Agent"] = "PANDA.1/0.2.11"
        if self.api_key:
            self._session.headers["Authorization"] = f"Bearer {self.api_key}"

        logger.info(f"ECHO client initialized: {self.base_url}")

    @property
    def is_throttled(self) -> bool:
        if self._consecutive_failures >= 3:
            elapsed = time.time() - self._last_error_time
            if elapsed < self._throttle_interval:
                return True
            self._consecutive_failures = 0
        return False

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        self._last_error_time = time.time()

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def health_check(self) -> Dict[str, Any]:
        result = {
            "healthy": False,
            "url": self.base_url,
            "error": None,
        }

        if self.is_throttled:
            result["error"] = "ECHO temporarily throttled after failures."
            return result

        try:
            response = self._session.get(
                f"{self.base_url}/health",
                timeout=self.timeout,
            )
            if response.status_code == 200:
                result["healthy"] = True
                result["data"] = response.json()
                self._record_success()
            else:
                result["error"] = f"Status {response.status_code}"
                self._record_failure()
        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to ECHO at {self.base_url}"
            self._record_failure()
        except requests.exceptions.Timeout:
            result["error"] = f"Connection timeout ({self.timeout}s)"
            self._record_failure()
        except Exception as exc:
            result["error"] = str(exc)
            self._record_failure()

        return result

    def is_healthy(self) -> bool:
        return self.health_check().get("healthy", False)

    def query(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        if self.is_throttled:
            return {"success": False, "error": "ECHO throttled after failures."}

        payload = {"query": query, "top_k": top_k}
        try:
            response = self._session.post(
                f"{self.base_url}/query",
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code == 200:
                self._record_success()
                return {"success": True, "results": response.json().get("results", [])}
            self._record_failure()
            return {"success": False, "error": f"Status {response.status_code}"}
        except requests.exceptions.ConnectionError:
            self._record_failure()
            return {"success": False, "error": "ECHO connection error"}
        except requests.exceptions.Timeout:
            self._record_failure()
            return {"success": False, "error": "ECHO connection timeout"}
        except Exception as exc:
            self._record_failure()
            return {"success": False, "error": str(exc)}

