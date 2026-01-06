"""
PANDA.1 Intent Detector
=======================
Detects user intent for routing to appropriate handlers.

Version: 0.2.11

Supported intents:
- news: News-related queries (routes to SCOTT)
- weather: Weather queries
- reminder: Task/reminder requests
- general: Default LLM handling
"""

import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class IntentDetector:
    """
    Simple intent detection using pattern matching.
    
    Routes queries to appropriate handlers:
    - News → SCOTT agent
    - Weather → Weather service
    - General → LLM
    """
    
    # Intent patterns (compiled for performance)
    PATTERNS = {
        "panda_learn": [
            r"^panda learn\b",
            r"^panda,\s*learn\b",
        ],
        "news": [
            r"\bnews\b",
            r"\bheadlines?\b",
            r"\bwhat'?s happening\b",
            r"\bcurrent events?\b",
            r"\btop stories\b",
            r"\bbreaking\b",
            r"\blatest\b.*\b(?:news|stories|events)\b",
        ],
        "weather": [
            r"\bweather\b",
            r"\bforecast\b",
            r"\btemperature\b",
            r"\bwill it rain\b",
            r"\bhow hot\b",
            r"\bhow cold\b",
        ],
        "reminder": [
            r"\bremind me\b",
            r"\bset (?:a )?reminder\b",
            r"\bdon'?t forget\b",
            r"\btask\b",
            r"\btodo\b",
        ],
        "time": [
            r"\bwhat time\b",
            r"\bcurrent time\b",
            r"\bwhat'?s the time\b",
        ],
        "identity": [
            r"\bwho am i\b",
            r"\bmy name\b",
            r"\bwhat do i do\b",
            r"\bmy business\b",
        ],
    }
    
    def __init__(self):
        """Initialize intent detector with compiled patterns."""
        self._compiled = {}
        for intent, patterns in self.PATTERNS.items():
            self._compiled[intent] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
        logger.info("Intent detector initialized")
    
    def detect(self, text: str) -> Optional[str]:
        """
        Detect the primary intent of user input.
        
        Args:
            text: User input text
        
        Returns:
            Intent name or None for general
        """
        text = text.strip().lower()
        
        # Check each intent's patterns
        for intent, patterns in self._compiled.items():
            for pattern in patterns:
                if pattern.search(text):
                    logger.debug(f"Detected intent: {intent}")
                    return intent
        
        return None  # General/default
    
    def detect_with_confidence(self, text: str) -> Tuple[Optional[str], float]:
        """
        Detect intent with confidence score.
        
        Args:
            text: User input text
        
        Returns:
            Tuple of (intent, confidence)
        """
        text = text.strip().lower()
        
        matches = {}
        for intent, patterns in self._compiled.items():
            match_count = sum(1 for p in patterns if p.search(text))
            if match_count > 0:
                matches[intent] = match_count / len(patterns)
        
        if not matches:
            return None, 0.0
        
        # Return highest confidence match
        best_intent = max(matches, key=matches.get)
        return best_intent, matches[best_intent]
    
    def extract_entities(self, text: str, intent: str) -> dict:
        """
        Extract relevant entities based on detected intent.
        
        Args:
            text: User input text
            intent: Detected intent
        
        Returns:
            Dict of extracted entities
        """
        entities = {}
        
        if intent == "news":
            # Extract topic and count
            count_match = re.search(r'\b(\d+)\b', text)
            if count_match:
                entities["count"] = int(count_match.group(1))
            
            # Common news topics
            topics = [
                "world",
                "us",
                "los angeles",
                "la weather",
                "entertainment",
                "china",
                "tech",
                "business",
                "science",
                "sports",
                "mlb",
                "korea",
                "koreanews",
                "ai",
            ]
            for topic in topics:
                if topic in text.lower():
                    entities["topic"] = topic
                    break
        
        elif intent == "weather":
            # Extract location
            location_match = re.search(r'(?:in|for|at)\s+([A-Za-z\s]+)', text)
            if location_match:
                entities["location"] = location_match.group(1).strip()
        
        elif intent == "reminder":
            # Extract time
            time_match = re.search(
                r'(?:in|at|tomorrow|tonight)\s*(\d+\s*(?:minutes?|hours?|days?))?',
                text
            )
            if time_match:
                entities["time"] = time_match.group(0).strip()
        
        return entities
