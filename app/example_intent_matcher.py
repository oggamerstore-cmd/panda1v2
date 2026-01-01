"""
PANDA.1 Example Intent Matcher
==============================
Matches user input against intent examples using fuzzy string matching.

Version: 0.2.4

Uses rapidfuzz for fast fuzzy string matching.
Falls back to basic matching if rapidfuzz not installed.
"""

import logging
import re
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass

from intent_examples_loader import get_intent_loader, IntentExample

logger = logging.getLogger(__name__)

# Try to import rapidfuzz
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
    logger.debug("rapidfuzz available for intent matching")
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    logger.warning("rapidfuzz not installed. Using basic matching. Install: pip install rapidfuzz")


@dataclass
class MatchResult:
    """Result of intent matching."""
    intent: Optional[str]
    category: Optional[str]
    confidence: float
    matched_example: Optional[str]
    routing_target: Optional[str]  # news, finance, general, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "category": self.category,
            "confidence": self.confidence,
            "matched_example": self.matched_example,
            "routing_target": self.routing_target,
        }


class ExampleIntentMatcher:
    """
    Matches user input to intent examples using fuzzy matching.
    
    Routes:
    - news/headlines → SCOTT
    - finance/money → PENNY
    - meta/system/tasks → Local handling
    - general → LLM
    """
    
    # Category to routing target mapping
    CATEGORY_ROUTING = {
        # News categories
        "news": "scott",
        "headlines": "scott",
        "current_events": "scott",
        # Finance categories
        "finance": "penny",
        "money": "penny",
        "accounting": "penny",
        "business_finance": "penny",
        # Meta/system categories
        "meta": "local",
        "system": "local",
        "tasks": "local",
        "docs": "local",
        # General
        "general_meta": "llm",
        "general": "llm",
    }
    
    # Intent prefixes to routing
    INTENT_ROUTING = {
        "news.": "scott",
        "finance.": "penny",
        "money.": "penny",
        "accounting.": "penny",
        "tasks.": "local",
        "system.": "local",
        "assistant.": "llm",
        "docs.": "local",
    }
    
    def __init__(self, confidence_threshold: float = 0.65):
        """
        Initialize the matcher.
        
        Args:
            confidence_threshold: Minimum confidence for a match (0-1)
        """
        self.threshold = confidence_threshold
        self.loader = get_intent_loader()
        self._utterances_cache: Optional[List[str]] = None
        self._examples_map: Dict[str, IntentExample] = {}
        
        # Build cache
        self._build_cache()
    
    def _build_cache(self) -> None:
        """Build the utterance cache for matching."""
        self._utterances_cache = []
        self._examples_map = {}
        
        for example in self.loader.examples:
            utterance = example.utterance.lower().strip()
            self._utterances_cache.append(utterance)
            self._examples_map[utterance] = example
    
    def _get_routing_target(self, example: IntentExample) -> str:
        """Determine routing target from example."""
        # Check category first
        if example.category:
            category = example.category.lower()
            for cat_pattern, target in self.CATEGORY_ROUTING.items():
                if cat_pattern in category:
                    return target
        
        # Check intent prefix
        if example.intent:
            intent = example.intent.lower()
            for prefix, target in self.INTENT_ROUTING.items():
                if intent.startswith(prefix):
                    return target
        
        return "llm"  # Default to LLM
    
    def match(self, user_input: str) -> MatchResult:
        """
        Match user input against intent examples.
        
        Args:
            user_input: User's input text
        
        Returns:
            MatchResult with intent, category, confidence, and routing
        """
        if not user_input or not self._utterances_cache:
            return MatchResult(
                intent=None,
                category=None,
                confidence=0.0,
                matched_example=None,
                routing_target="llm"
            )
        
        input_lower = user_input.lower().strip()
        
        if RAPIDFUZZ_AVAILABLE:
            return self._match_with_rapidfuzz(input_lower)
        else:
            return self._match_basic(input_lower)
    
    def _match_with_rapidfuzz(self, input_lower: str) -> MatchResult:
        """Match using rapidfuzz library."""
        # Use extractOne for best match
        result = process.extractOne(
            input_lower,
            self._utterances_cache,
            scorer=fuzz.token_set_ratio,  # Good for reordered/partial matches
            score_cutoff=int(self.threshold * 100)
        )
        
        if result is None:
            return MatchResult(
                intent=None,
                category=None,
                confidence=0.0,
                matched_example=None,
                routing_target="llm"
            )
        
        matched_text, score, _ = result
        confidence = score / 100.0
        
        example = self._examples_map.get(matched_text)
        
        if example:
            return MatchResult(
                intent=example.intent,
                category=example.category,
                confidence=confidence,
                matched_example=matched_text,
                routing_target=self._get_routing_target(example)
            )
        
        return MatchResult(
            intent=None,
            category=None,
            confidence=confidence,
            matched_example=matched_text,
            routing_target="llm"
        )
    
    def _match_basic(self, input_lower: str) -> MatchResult:
        """Basic matching without rapidfuzz (slower, less accurate)."""
        best_match = None
        best_score = 0.0
        
        input_words = set(input_lower.split())
        
        for utterance in self._utterances_cache:
            utt_words = set(utterance.split())
            
            # Jaccard similarity
            intersection = len(input_words & utt_words)
            union = len(input_words | utt_words)
            
            if union > 0:
                score = intersection / union
                if score > best_score:
                    best_score = score
                    best_match = utterance
        
        if best_score < self.threshold or best_match is None:
            return MatchResult(
                intent=None,
                category=None,
                confidence=0.0,
                matched_example=None,
                routing_target="llm"
            )
        
        example = self._examples_map.get(best_match)
        
        if example:
            return MatchResult(
                intent=example.intent,
                category=example.category,
                confidence=best_score,
                matched_example=best_match,
                routing_target=self._get_routing_target(example)
            )
        
        return MatchResult(
            intent=None,
            category=None,
            confidence=best_score,
            matched_example=best_match,
            routing_target="llm"
        )
    
    def get_top_matches(
        self, 
        user_input: str, 
        limit: int = 5
    ) -> List[MatchResult]:
        """
        Get top N matching intents.
        
        Args:
            user_input: User's input text
            limit: Maximum matches to return
        
        Returns:
            List of MatchResults sorted by confidence
        """
        if not user_input or not self._utterances_cache:
            return []
        
        input_lower = user_input.lower().strip()
        
        if RAPIDFUZZ_AVAILABLE:
            results = process.extract(
                input_lower,
                self._utterances_cache,
                scorer=fuzz.token_set_ratio,
                limit=limit
            )
            
            matches = []
            for matched_text, score, _ in results:
                confidence = score / 100.0
                example = self._examples_map.get(matched_text)
                
                if example:
                    matches.append(MatchResult(
                        intent=example.intent,
                        category=example.category,
                        confidence=confidence,
                        matched_example=matched_text,
                        routing_target=self._get_routing_target(example)
                    ))
            
            return matches
        
        # Fallback: just return single best match
        single = self.match(user_input)
        return [single] if single.confidence > 0 else []
    
    def get_status(self) -> Dict[str, Any]:
        """Get matcher status."""
        return {
            "rapidfuzz_available": RAPIDFUZZ_AVAILABLE,
            "threshold": self.threshold,
            "total_examples": len(self._utterances_cache or []),
            "loader_status": self.loader.get_status(),
        }


# Global matcher instance
_matcher: Optional[ExampleIntentMatcher] = None


def get_intent_matcher() -> ExampleIntentMatcher:
    """Get the global intent matcher."""
    global _matcher
    
    if _matcher is None:
        from config import get_config
        config = get_config()
        _matcher = ExampleIntentMatcher(
            confidence_threshold=config.intent_confidence_threshold
        )
    
    return _matcher


def match_intent(user_input: str) -> MatchResult:
    """
    Match user input to an intent.
    
    Args:
        user_input: User's input text
    
    Returns:
        MatchResult with intent and routing info
    """
    return get_intent_matcher().match(user_input)


def get_routing_target(user_input: str) -> Tuple[str, float]:
    """
    Get the routing target for user input.
    
    Args:
        user_input: User's input text
    
    Returns:
        Tuple of (routing_target, confidence)
    """
    result = match_intent(user_input)
    return result.routing_target, result.confidence
