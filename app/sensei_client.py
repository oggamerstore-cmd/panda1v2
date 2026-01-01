"""
PANDA.1 SENSEI Client
=====================
Client for communicating with SENSEI (Smart Educational Network for
Systematic Enlightenment & Intelligence) learning hub.

Version: 0.2.10

Network Configuration:
- SENSEI runs on 192.168.1.19:8002
- Configure via PANDA_SENSEI_API_URL environment variable

Features:
- Download lesson data from SENSEI
- Store learned content in PANDA's memory system
- Deep learning integration for knowledge acquisition
"""

import logging
from typing import List, Dict, Optional, Any

import requests

logger = logging.getLogger(__name__)


class SenseiClient:
    """
    Client for SENSEI learning hub API.

    SENSEI is a separate service running on the local network
    that collects and serves educational content/lessons.
    """

    def __init__(self, base_url: str, timeout: int = 15, api_key: str = ""):
        """
        Initialize SENSEI client.

        Args:
            base_url: SENSEI API base URL (e.g., http://192.168.1.19:8002)
            timeout: Request timeout in seconds
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.api_key = api_key
        self._session = requests.Session()

        if api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

        logger.info(f"SENSEI client initialized: {self.base_url}")

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

        try:
            response = self._session.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )

            if response.status_code == 200:
                result["healthy"] = True
                result["data"] = response.json()
            else:
                result["error"] = f"Status {response.status_code}"

        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to SENSEI at {self.base_url}"
            logger.warning(f"SENSEI connection error: {self.base_url}/health")
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout"
        except Exception as e:
            result["error"] = str(e)

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
            else:
                result["error"] = f"Status {response.status_code}"

        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to SENSEI"
            logger.error(f"SENSEI connection error: {self.base_url}/api/lessons")
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout"
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"SENSEI error: {e}")

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

        try:
            response = self._session.get(
                f"{self.base_url}/api/lessons/{lesson_id}",
                timeout=self.timeout
            )

            if response.status_code == 200:
                result["success"] = True
                result["lesson"] = response.json()
            elif response.status_code == 404:
                result["error"] = f"Lesson {lesson_id} not found"
            else:
                result["error"] = f"Status {response.status_code}"

        except requests.exceptions.ConnectionError:
            result["error"] = "Cannot connect to SENSEI"
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout"
        except Exception as e:
            result["error"] = str(e)

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

        try:
            params = {}
            if topic:
                params["topic"] = topic

            response = self._session.get(
                f"{self.base_url}/api/knowledge/download",
                params=params,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                result["success"] = True
                result["knowledge"] = data.get("knowledge", data.get("items", []))
                result["count"] = len(result["knowledge"])
                result["source"] = "sensei"
                logger.info(f"Downloaded {result['count']} knowledge items from SENSEI")
            else:
                result["error"] = f"Status {response.status_code}"

        except requests.exceptions.ConnectionError:
            result["error"] = "Cannot connect to SENSEI"
            logger.error(f"SENSEI connection error during knowledge download")
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout - SENSEI may have a lot of data"
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"SENSEI knowledge download error: {e}")

        return result

    def get_categories(self) -> List[str]:
        """
        Get available lesson categories.

        Returns:
            List of category names
        """
        try:
            response = self._session.get(
                f"{self.base_url}/api/categories",
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("categories", [])
            return []

        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
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

            return response.status_code in (200, 201)

        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}")
            return False


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
