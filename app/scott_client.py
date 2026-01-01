"""
PANDA.1 SCOTT Client
====================
Client for communicating with SCOTT (Smart Curator Of Today's Topics) news agent.

Version: 0.2.3

Network Configuration:
- SCOTT runs on 192.168.1.18:8000
- Configure via PANDA_SCOTT_API_URL environment variable
"""

import logging
from typing import List, Dict, Optional, Any

import requests

logger = logging.getLogger(__name__)


class ScottClient:
    """
    Client for SCOTT news agent API.
    
    SCOTT is a separate service running on the local network
    that curates and serves news articles.
    """
    
    def __init__(self, base_url: str, timeout: int = 10):
        """
        Initialize SCOTT client.
        
        Args:
            base_url: SCOTT API base URL (e.g., http://192.168.1.18:8000/api)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        logger.info(f"SCOTT client initialized: {self.base_url}")
    
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
        
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result["healthy"] = True
                result["data"] = response.json()
            else:
                result["error"] = f"Status {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            result["error"] = f"Cannot connect to SCOTT at {self.base_url}"
            logger.error(f"SCOTT connection error: {self.base_url}/health")
        except requests.exceptions.Timeout:
            result["error"] = "Connection timeout"
        except Exception as e:
            result["error"] = str(e)
        
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
        try:
            params = {"limit": limit}
            if topic:
                params["topic"] = topic
            
            response = requests.get(
                f"{self.base_url}/articles/top",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("articles", data) if isinstance(data, dict) else data
            else:
                logger.warning(f"SCOTT returned status {response.status_code}")
                return []
                
        except requests.exceptions.ConnectionError:
            logger.error(f"SCOTT connection error: {self.base_url}/articles/top")
            return []
        except Exception as e:
            logger.error(f"SCOTT error: {e}")
            return []
    
    def get_topics(self) -> List[Dict]:
        """
        Get available news topics.
        
        Returns:
            List of topic dicts with slug and name
        """
        try:
            response = requests.get(
                f"{self.base_url}/topics",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("topics", data) if isinstance(data, dict) else data
            return []
            
        except Exception as e:
            logger.error(f"Failed to get topics: {e}")
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
        try:
            response = requests.get(
                f"{self.base_url}/articles/topic/{topic}",
                params={"limit": limit},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("articles", data) if isinstance(data, dict) else data
            return []
            
        except Exception as e:
            logger.error(f"Failed to get articles for topic {topic}: {e}")
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
        try:
            response = requests.get(
                f"{self.base_url}/articles/search",
                params={"q": query, "limit": limit},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("articles", data) if isinstance(data, dict) else data
            return []
            
        except Exception as e:
            logger.error(f"Article search failed: {e}")
            return []
