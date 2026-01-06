"""
PANDA.1 Intent Examples Loader
==============================
Loads intent examples from JSONL files for fuzzy matching.

Version: 0.2.11
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class IntentExample:
    """Represents a single intent example."""
    
    def __init__(
        self, 
        utterance: str, 
        intent: Optional[str] = None, 
        category: Optional[str] = None
    ):
        self.utterance = utterance
        self.intent = intent
        self.category = category
    
    def __repr__(self):
        return f"IntentExample('{self.utterance[:30]}...', intent={self.intent}, cat={self.category})"


class IntentExamplesLoader:
    """
    Loads intent examples from JSONL files.
    
    JSONL format:
    {"utterance": "...", "intent": "...", "category": "..."}
    or
    {"utterance": "...", "category": "..."}
    """
    
    def __init__(self):
        self.examples: List[IntentExample] = []
        self._by_category: Dict[str, List[IntentExample]] = {}
        self._by_intent: Dict[str, List[IntentExample]] = {}
    
    def load_file(self, filepath: Path) -> int:
        """
        Load examples from a single JSONL file.
        
        Args:
            filepath: Path to JSONL file
        
        Returns:
            Number of examples loaded
        """
        if not filepath.exists():
            logger.warning(f"Intent file not found: {filepath}")
            return 0
        
        count = 0
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        utterance = data.get('utterance', '').strip()
                        
                        if not utterance:
                            continue
                        
                        example = IntentExample(
                            utterance=utterance,
                            intent=data.get('intent'),
                            category=data.get('category')
                        )
                        
                        self.examples.append(example)
                        
                        # Index by category
                        if example.category:
                            if example.category not in self._by_category:
                                self._by_category[example.category] = []
                            self._by_category[example.category].append(example)
                        
                        # Index by intent
                        if example.intent:
                            if example.intent not in self._by_intent:
                                self._by_intent[example.intent] = []
                            self._by_intent[example.intent].append(example)
                        
                        count += 1
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON at {filepath}:{line_num}: {e}")
                        continue
            
            logger.info(f"Loaded {count} examples from {filepath.name}")
            
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
        
        return count
    
    def load_directory(self, dirpath: Path, pattern: str = "*.jsonl") -> int:
        """
        Load all JSONL files from a directory.
        
        Args:
            dirpath: Directory path
            pattern: File pattern to match
        
        Returns:
            Total number of examples loaded
        """
        if not dirpath.exists():
            logger.warning(f"Intent directory not found: {dirpath}")
            return 0
        
        total = 0
        for filepath in sorted(dirpath.glob(pattern)):
            total += self.load_file(filepath)
        
        logger.info(f"Total examples loaded: {total}")
        return total
    
    def get_examples(
        self, 
        category: Optional[str] = None,
        intent: Optional[str] = None
    ) -> List[IntentExample]:
        """
        Get examples, optionally filtered.
        
        Args:
            category: Filter by category
            intent: Filter by intent
        
        Returns:
            List of matching examples
        """
        if intent:
            return self._by_intent.get(intent, [])
        if category:
            return self._by_category.get(category, [])
        return self.examples
    
    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        return list(self._by_category.keys())
    
    def get_intents(self) -> List[str]:
        """Get all unique intents."""
        return list(self._by_intent.keys())
    
    def get_utterances(self) -> List[str]:
        """Get all utterances for matching."""
        return [e.utterance for e in self.examples]
    
    def get_status(self) -> Dict[str, Any]:
        """Get loader status."""
        return {
            "total_examples": len(self.examples),
            "categories": len(self._by_category),
            "intents": len(self._by_intent),
            "category_names": list(self._by_category.keys()),
        }


# Default paths for intent files
def get_default_intent_paths() -> List[Path]:
    """Get default paths to look for intent files."""
    
    paths = []
    
    # Check installation directory
    install_dir = Path.home() / ".local" / "share" / "panda1" / "intents"
    if install_dir.exists():
        paths.append(install_dir)
    
    # Check relative to script
    script_dir = Path(__file__).parent / "intents"
    if script_dir.exists() and script_dir not in paths:
        paths.append(script_dir)
    
    return paths


# Global loader instance
_intent_loader: Optional[IntentExamplesLoader] = None


def get_intent_loader() -> IntentExamplesLoader:
    """Get the global intent examples loader."""
    global _intent_loader
    
    if _intent_loader is None:
        _intent_loader = IntentExamplesLoader()
        
        # Load from default paths
        for path in get_default_intent_paths():
            _intent_loader.load_directory(path)
        
        if not _intent_loader.examples:
            logger.warning("No intent examples loaded")
    
    return _intent_loader


def load_intents_from_path(path: Path) -> int:
    """
    Load intents from a specific path.
    
    Args:
        path: File or directory path
    
    Returns:
        Number of examples loaded
    """
    loader = get_intent_loader()
    
    if path.is_file():
        return loader.load_file(path)
    elif path.is_dir():
        return loader.load_directory(path)
    return 0
