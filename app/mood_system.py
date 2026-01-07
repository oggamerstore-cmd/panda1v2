"""
PANDA.1 Mood System
===================
Manages PANDA.1's emotional state for GUI visualization.

Version: 2.0

Mood states affect the GUI's color scheme and response style.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timedelta
import random

logger = logging.getLogger(__name__)


class MoodSystem:
    """
    Manages PANDA.1's mood state for GUI visualization.
    
    Moods affect:
    - GUI orb color
    - Response tone (subtle)
    - Greeting style
    """
    
    # Mood definitions with colors
    MOODS = {
        "neutral": {
            "color": "#00d4ff",  # Cyan
            "description": "Calm and ready",
            "energy": 0.5
        },
        "happy": {
            "color": "#00ff88",  # Green
            "description": "Positive and upbeat",
            "energy": 0.8
        },
        "focused": {
            "color": "#ff9500",  # Orange
            "description": "Deep in thought",
            "energy": 0.7
        },
        "curious": {
            "color": "#a855f7",  # Purple
            "description": "Interested and engaged",
            "energy": 0.6
        },
        "tired": {
            "color": "#6b7280",  # Gray
            "description": "Low energy",
            "energy": 0.3
        },
        "excited": {
            "color": "#f43f5e",  # Pink/Red
            "description": "High energy",
            "energy": 0.9
        }
    }
    
    def __init__(self):
        """Initialize the mood system."""
        self.current_mood = "neutral"
        self._last_interaction = datetime.now()
        self._interaction_count = 0
        self._mood_locked = False
        self._mood_lock_until = None
        
        logger.info("Mood system initialized")
    
    def get_state(self) -> Dict[str, Any]:
        """
        Get current mood state.
        
        Returns:
            Dict with mood name, color, description, and energy
        """
        mood_data = self.MOODS.get(self.current_mood, self.MOODS["neutral"])
        return {
            "mood": self.current_mood,
            "color": mood_data["color"],
            "description": mood_data["description"],
            "energy": mood_data["energy"]
        }
    
    def update(self, interaction_type: str = "chat", sentiment: float = 0.5) -> None:
        """
        Update mood based on interaction.
        
        Args:
            interaction_type: Type of interaction (chat, news, task, etc.)
            sentiment: Sentiment score 0-1 (0.5 = neutral)
        """
        if self._is_locked():
            return
        
        self._last_interaction = datetime.now()
        self._interaction_count += 1
        
        # Simple mood transitions
        if sentiment > 0.7:
            self._transition_to("happy", 0.3)
        elif sentiment < 0.3:
            self._transition_to("tired", 0.2)
        elif interaction_type == "news":
            self._transition_to("curious", 0.4)
        elif self._interaction_count > 10:
            self._transition_to("focused", 0.2)
    
    def _transition_to(self, target_mood: str, probability: float) -> None:
        """Probabilistic mood transition."""
        if random.random() < probability:
            if target_mood in self.MOODS:
                self.current_mood = target_mood
                logger.debug(f"Mood transitioned to: {target_mood}")
    
    def _is_locked(self) -> bool:
        """Check if mood is temporarily locked."""
        if not self._mood_locked:
            return False
        if self._mood_lock_until and datetime.now() > self._mood_lock_until:
            self._mood_locked = False
            return False
        return True
    
    def set_mood(self, mood: str, lock_minutes: int = 0) -> bool:
        """
        Manually set mood state.
        
        Args:
            mood: Mood name
            lock_minutes: Lock mood for this many minutes
        
        Returns:
            True if successful
        """
        if mood not in self.MOODS:
            return False
        
        self.current_mood = mood
        
        if lock_minutes > 0:
            self._mood_locked = True
            self._mood_lock_until = datetime.now() + timedelta(minutes=lock_minutes)
        
        logger.info(f"Mood set to: {mood}")
        return True
    
    def reset(self) -> None:
        """Reset mood to neutral."""
        self.current_mood = "neutral"
        self._mood_locked = False
        self._mood_lock_until = None
        self._interaction_count = 0
