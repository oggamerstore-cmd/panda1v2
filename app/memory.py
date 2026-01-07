"""
PANDA.1 Memory System
=====================
Handles persistent memory storage using ChromaDB for semantic search.

Version: 2.0

Features:
- Semantic search over stored memories
- Identity awareness (knows BOS's info)
- ChromaDB telemetry disabled by default
"""

import json
import logging
import math
import os
import sqlite3
import threading
import uuid
from array import array
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable, Iterable

from .config import get_config

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


def parse_sensei_jsonl(file_path: Path) -> List[Dict[str, Any]]:
    """
    Parse SENSEI knowledge_injections.jsonl into normalized docs.

    Each line should be JSON with required fields:
    - id
    - title or summary
    """
    docs: List[Dict[str, Any]] = []
    if not file_path.exists():
        logger.warning("SENSEI JSONL file not found: %s", file_path)
        return docs

    with open(file_path, "r", encoding="utf-8") as handle:
        for line_num, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Invalid JSON in SENSEI JSONL at line %s: %s", line_num, exc)
                continue

            injection_id = str(data.get("id", "")).strip()
            title = str(data.get("title", "")).strip()
            summary = str(data.get("summary", "")).strip()

            if not injection_id:
                logger.warning("Skipping SENSEI JSONL line %s: missing id", line_num)
                continue
            if not title and not summary:
                logger.warning("Skipping SENSEI JSONL line %s: missing title/summary", line_num)
                continue

            tags_value = data.get("tags", [])
            if isinstance(tags_value, str):
                tags = [t.strip() for t in tags_value.split(",") if t.strip()]
            elif isinstance(tags_value, list):
                tags = [str(tag).strip() for tag in tags_value if str(tag).strip()]
            else:
                tags = []

            combined_text = f"{title}\n\n{summary}\n\nTags: {', '.join(tags)}"
            normalized_title = title or summary

            docs.append(
                {
                    "injection_id": injection_id,
                    "title": normalized_title,
                    "tags": tags,
                    "text": combined_text,
                }
            )

    return docs


class SenseiVectorMemory:
    """
    Persistent vector memory for SENSEI knowledge injections.
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        embedder: Optional[Callable[[List[str]], List[List[float]]]] = None,
    ):
        self.config = get_config()
        self.base_dir = base_dir or (self.config.base_dir / "memory" / "sensei")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "index.sqlite"
        self._lock = threading.Lock()
        self._embedder = embedder
        self._embedding_cache: Optional[List[Dict[str, Any]]] = None
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sensei_docs (
                    injection_id TEXT PRIMARY KEY,
                    title TEXT,
                    tags_json TEXT,
                    text TEXT,
                    text_sha256 TEXT,
                    embedding BLOB,
                    dims INTEGER,
                    ingested_at TEXT
                )
                """
            )
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _hash_text(self, text: str) -> str:
        return sha256(text.encode("utf-8")).hexdigest()

    def _embedding_to_blob(self, embedding: List[float]) -> bytes:
        arr = array("f", embedding)
        return arr.tobytes()

    def _blob_to_embedding(self, blob: bytes) -> List[float]:
        arr = array("f")
        arr.frombytes(blob)
        return list(arr)

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        if self._embedder:
            return self._embedder(texts)

        embeddings: List[List[float]] = []
        for text in texts:
            embedding = self._ollama_embed(text)
            embeddings.append(embedding)
        return embeddings

    def _ollama_embed(self, text: str) -> List[float]:
        import requests

        url = f"{self.config.ollama_host}/api/embeddings"
        payload = {"model": self.config.ollama_embed_model, "prompt": text}
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        embedding = data.get("embedding")
        if not isinstance(embedding, list):
            raise ValueError("Invalid embedding response from Ollama")
        return [float(x) for x in embedding]

    def ingest_docs(self, docs: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        inserted = 0
        updated = 0
        skipped = 0

        docs_list = list(docs)
        if not docs_list:
            return {
                "inserted": inserted,
                "updated": updated,
                "skipped": skipped,
                "total": self.count(),
            }

        with self._lock:
            with self._get_connection() as conn:
                for doc in docs_list:
                    injection_id = doc["injection_id"]
                    text = doc["text"]
                    text_hash = self._hash_text(text)

                    row = conn.execute(
                        "SELECT text_sha256 FROM sensei_docs WHERE injection_id = ?",
                        (injection_id,),
                    ).fetchone()

                    if row and row[0] == text_hash:
                        skipped += 1
                        continue

                    try:
                        embedding = self._embed_texts([text])[0]
                    except Exception as exc:
                        logger.warning("SENSEI embedding failed for %s: %s", injection_id, exc)
                        skipped += 1
                        continue

                    embedding_blob = self._embedding_to_blob(embedding)
                    dims = len(embedding)
                    tags_json = json.dumps(doc.get("tags", []))
                    now = datetime.utcnow().isoformat()

                    if row:
                        conn.execute(
                            """
                            UPDATE sensei_docs
                            SET title = ?, tags_json = ?, text = ?, text_sha256 = ?,
                                embedding = ?, dims = ?, ingested_at = ?
                            WHERE injection_id = ?
                            """,
                            (
                                doc.get("title", ""),
                                tags_json,
                                text,
                                text_hash,
                                embedding_blob,
                                dims,
                                now,
                                injection_id,
                            ),
                        )
                        updated += 1
                    else:
                        conn.execute(
                            """
                            INSERT INTO sensei_docs (
                                injection_id, title, tags_json, text, text_sha256,
                                embedding, dims, ingested_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                injection_id,
                                doc.get("title", ""),
                                tags_json,
                                text,
                                text_hash,
                                embedding_blob,
                                dims,
                                now,
                            ),
                        )
                        inserted += 1

                conn.commit()

        if inserted or updated:
            self._embedding_cache = None

        total = self.count()
        logger.info(
            "SENSEI ingest complete",
            extra={"inserted": inserted, "updated": updated, "skipped": skipped, "total": total},
        )
        return {
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "total": total,
        }

    def _load_embedding_cache(self) -> None:
        cache: List[Dict[str, Any]] = []
        with self._lock:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT injection_id, title, text, embedding FROM sensei_docs"
                ).fetchall()
                for injection_id, title, text, embedding_blob in rows:
                    if embedding_blob is None:
                        continue
                    cache.append(
                        {
                            "injection_id": injection_id,
                            "title": title,
                            "text": text,
                            "embedding": self._blob_to_embedding(embedding_blob),
                        }
                    )
        self._embedding_cache = cache

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not query.strip():
            return []

        if self._embedding_cache is None:
            self._load_embedding_cache()

        if not self._embedding_cache:
            return []

        try:
            query_embedding = self._embed_texts([query])[0]
        except Exception as exc:
            logger.warning("SENSEI query embedding failed: %s", exc)
            return []

        query_norm = math.sqrt(sum(v * v for v in query_embedding)) or 1.0

        scored: List[Dict[str, Any]] = []
        for item in self._embedding_cache:
            vector = item["embedding"]
            dot = sum(a * b for a, b in zip(query_embedding, vector))
            denom = query_norm * (math.sqrt(sum(v * v for v in vector)) or 1.0)
            score = dot / denom
            scored.append({**item, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        results: List[Dict[str, Any]] = []
        for item in scored[:top_k]:
            snippet = " ".join(item["text"].split())[:200]
            results.append(
                {
                    "injection_id": item["injection_id"],
                    "title": item["title"],
                    "snippet": snippet,
                }
            )
        return results

    def count(self) -> int:
        with self._lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT COUNT(*) FROM sensei_docs").fetchone()
                return int(row[0]) if row else 0
