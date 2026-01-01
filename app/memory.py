"""
PANDA.1 Memory System
=====================
Handles persistent memory storage using ChromaDB for semantic search.

Version: 0.2.10

Features:
- Semantic search over stored memories
- Identity awareness (knows BOS's info)
- ChromaDB telemetry disabled by default
"""

import logging
import os
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid

from config import get_config

logger = logging.getLogger(__name__)

# Disable ChromaDB telemetry before import
os.environ["ANONYMIZED_TELEMETRY"] = "false"


class MemorySystem:
    """
    Memory system using ChromaDB for semantic storage and retrieval.
    
    Features:
    - Semantic search over stored memories
    - Memory types (fact, preference, task, general)
    - BOS identity pre-seeded
    """
    
    # BOS identity facts to seed on first run
    IDENTITY_SEEDS = [
        "BOS's real name is Jong Sun Kim, also known as James Kim.",
        "BOS is a Korean-American entrepreneur.",
        "BOS runs JNJ Foods LLC.",
        "BOS's brands include: Mama Kim's Kimchi, Mama Kim's Korean BBQ, Moka's Matcha, OG Gamer Store, Sticky Creations.",
        "BOS is passionate about computers, AI, servers, electronics, and digital art.",
        "BOS uses Ubuntu 24.04 on his home server named PANDA.1.",
    ]
    
    def __init__(self):
        """Initialize the memory system."""
        self.config = get_config()
        self._client = None
        self._collection = None
        self.is_available = False
        self._disabled_reason: Optional[str] = None
        
        if self.config.enable_memory:
            self._initialize_chromadb()
    
    def _initialize_chromadb(self) -> None:
        """Initialize ChromaDB client and collection."""
        try:
            import chromadb
            from chromadb.config import Settings
            
            # Disable telemetry
            settings = Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
            
            persist_dir = str(self.config.memory_dir / "chroma")
            
            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=settings
            )
            
            self._collection = self._client.get_or_create_collection(
                name=self.config.memory_collection,
                metadata={"hnsw:space": "cosine"}
            )
            
            self.is_available = True
            logger.info(f"ChromaDB initialized at {persist_dir}")
            
            # Seed identity on first run
            self._seed_identity()
            
        except ImportError:
            logger.warning("ChromaDB not installed. Memory disabled.")
            logger.info("Install with: pip install chromadb")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
    
    def _seed_identity(self) -> None:
        """Seed BOS identity facts if not already present."""
        if not self._collection:
            return
        
        try:
            # Check if already seeded
            existing = self._collection.get(where={"type": "identity"})
            if existing and existing.get("ids"):
                return  # Already seeded
            
            # Seed identity facts
            for fact in self.IDENTITY_SEEDS:
                if not self.store(fact, memory_type="identity"):
                    logger.warning("Memory seeding stopped due to store failure.")
                    break
            
            logger.info("BOS identity seeded in memory")
            
        except Exception as e:
            logger.warning(f"Could not seed identity: {e}")
    
    def store(
        self, 
        content: str, 
        memory_type: str = "general",
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Store a memory.
        
        Args:
            content: The memory content
            memory_type: Type of memory (fact, preference, task, general, identity)
            metadata: Additional metadata
        
        Returns:
            Memory ID
        """
        if not self.is_available or not self._collection:
            return ""
        
        try:
            memory_id = str(uuid.uuid4())
            
            meta = {
                "type": memory_type,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            }
            
            self._collection.add(
                documents=[content],
                metadatas=[meta],
                ids=[memory_id]
            )
            
            logger.debug(f"Stored memory: {memory_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            if self.is_available:
                self.is_available = False
                self._disabled_reason = str(e)
                logger.warning("Memory system disabled after store failure.")
            return ""
    
    def search(
        self, 
        query: str, 
        limit: int = 5,
        memory_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search memories by semantic similarity.
        
        Args:
            query: Search query
            limit: Max results
            memory_type: Filter by type (optional)
        
        Returns:
            List of matching memories
        """
        if not self.is_available or not self._collection:
            return []
        
        try:
            where = {"type": memory_type} if memory_type else None
            
            results = self._collection.query(
                query_texts=[query],
                n_results=limit,
                where=where
            )
            
            memories = []
            if results and results.get("documents"):
                docs = results["documents"][0]
                metas = results.get("metadatas", [[]])[0]
                ids = results.get("ids", [[]])[0]
                
                for doc, meta, mid in zip(docs, metas, ids):
                    memories.append({
                        "id": mid,
                        "content": doc,
                        "type": meta.get("type", "general"),
                        "timestamp": meta.get("timestamp")
                    })
            
            return memories
            
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return []
    
    def count(self) -> int:
        """Get total number of stored memories."""
        if not self.is_available or not self._collection:
            return 0
        
        try:
            return self._collection.count()
        except Exception as e:
            logging.error(f'Exception caught: {e}')
            return 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get memory system status."""
        return {
            "available": self.is_available,
            "enabled": self.config.enable_memory,
            "count": self.count() if self.is_available else 0,
            "collection": self.config.memory_collection,
            "path": str(self.config.memory_dir / "chroma") if self.is_available else None,
            "disabled_reason": self._disabled_reason
        }
    
    def clear(self) -> bool:
        """Clear all memories. Use with caution!"""
        if not self.is_available or not self._client:
            return False
        
        try:
            self._client.delete_collection(self.config.memory_collection)
            self._collection = self._client.create_collection(
                name=self.config.memory_collection,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Memory cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear memory: {e}")
            return False
