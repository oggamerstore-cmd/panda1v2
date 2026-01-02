"""
PANDA.1 Topic Resolution for SCOTT
==================================
Maps user input to SCOTT topic slugs.

Version: 0.2.3
"""

import re
from typing import Optional, List, Tuple


class TopicResolver:
    """
    Resolves user input to SCOTT topic slugs.
    
    Handles variations like:
    - "tech news" → "technology"
    - "what's happening in AI" → "ai"
    - "gaming headlines" → "gaming"
    """
    
    # Topic mappings: keyword patterns → SCOTT slug
    TOPIC_MAPPINGS = {
        "world": [
            r"\bworld\b",
            r"\binternational\b",
            r"\bglobal\b",
            r"\bforeign\b",
        ],
        "us": [
            r"\bus\b",
            r"\bu\.s\.\b",
            r"\bunited states\b",
            r"\bamerica\b",
            r"\bamerican\b",
        ],
        "los angeles": [
            r"\blos angeles\b",
            r"\bla\b",
            r"\bl\.a\.\b",
        ],
        "la weather": [
            r"\bla weather\b",
            r"\blos angeles weather\b",
        ],
        "entertainment": [
            r"\bentertainment\b",
            r"\bmovies?\b",
            r"\bmusic\b",
            r"\bcelebrity\b",
            r"\bhollywood\b",
        ],
        "china": [
            r"\bchina\b",
            r"\bbeijing\b",
            r"\bshanghai\b",
        ],
        "tech": [
            r"\btech\b",
            r"\btechnology\b",
            r"\bsoftware\b",
            r"\bhardware\b",
            r"\bcomputer\b",
        ],
        "ai": [
            r"\bai\b",
            r"\bartificial intelligence\b",
            r"\bmachine learning\b",
            r"\bml\b",
            r"\bllm\b",
            r"\bchatgpt\b",
            r"\bclaude\b",
        ],
        "business": [
            r"\bbusiness\b",
            r"\bfinance\b",
            r"\beconomy\b",
            r"\bmarket\b",
            r"\bstock\b",
            r"\binvest\b",
        ],
        "sports": [
            r"\bsports?\b",
            r"\bfootball\b",
            r"\bbasketball\b",
            r"\bbaseball\b",
            r"\bsoccer\b",
            r"\bnba\b",
            r"\bnfl\b",
        ],
        "mlb": [
            r"\bmlb\b",
            r"\bmajor league baseball\b",
        ],
        "science": [
            r"\bscience\b",
            r"\bresearch\b",
            r"\bdiscovery\b",
            r"\bspace\b",
            r"\bnasa\b",
        ],
        "korea": [
            r"\bkorea\b",
            r"\bsouth korea\b",
            r"\bseoul\b",
        ],
        "koreanews": [
            r"\bkorea news\b",
            r"\bkorean news\b",
            r"\bkoreanews\b",
        ],
    }
    
    def __init__(self):
        """Initialize with compiled patterns."""
        self._compiled = {}
        for topic, patterns in self.TOPIC_MAPPINGS.items():
            self._compiled[topic] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def resolve(self, text: str) -> Optional[str]:
        """
        Resolve user input to a SCOTT topic slug.
        
        Args:
            text: User input text
        
        Returns:
            Topic slug or None for general news
        """
        text = text.strip().lower()
        
        for topic, patterns in self._compiled.items():
            for pattern in patterns:
                if pattern.search(text):
                    return topic
        
        return None
    
    def resolve_all(self, text: str) -> List[str]:
        """
        Find all matching topics in input.
        
        Args:
            text: User input text
        
        Returns:
            List of matching topic slugs
        """
        text = text.strip().lower()
        matches = []
        
        for topic, patterns in self._compiled.items():
            for pattern in patterns:
                if pattern.search(text):
                    matches.append(topic)
                    break
        
        return matches
    
    def extract_count(self, text: str, default: int = 5) -> int:
        """
        Extract article count from user input.
        
        Args:
            text: User input text
            default: Default count if not specified
        
        Returns:
            Number of articles to retrieve
        """
        # Common patterns
        patterns = [
            r"(?:top|show|get|give me)\s+(\d+)",
            r"(\d+)\s+(?:news|articles?|stories|headlines?)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return min(int(match.group(1)), 20)  # Cap at 20
        
        return default
    
    def parse_news_request(self, text: str) -> Tuple[Optional[str], int]:
        """
        Parse a news request into topic and count.
        
        Args:
            text: User input text
        
        Returns:
            Tuple of (topic_slug, count)
        """
        topic = self.resolve(text)
        count = self.extract_count(text)
        return topic, count
    
    @classmethod
    def get_available_topics(cls) -> List[str]:
        """Get list of all available topic slugs."""
        return list(cls.TOPIC_MAPPINGS.keys())
