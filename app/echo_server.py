"""
ECHO Vector Database Server
===========================
FastAPI server that powers the ECHO database PC for PANDA.1.

Features:
- Qdrant-backed vector search with FastEmbed embeddings
- /health, /upsert, /query endpoints
- Optimized for 10k+ vectors on low-power CPUs
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "qdrant-client is required. Install with: pip install qdrant-client"
    ) from exc

try:
    from fastembed import TextEmbedding
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "fastembed is required. Install with: pip install fastembed"
    ) from exc

logger = logging.getLogger("echo_server")


@dataclass
class EchoSettings:
    base_dir: Path
    host: str
    port: int
    collection: str
    qdrant_url: Optional[str]
    qdrant_api_key: Optional[str]
    embed_model: str

    @classmethod
    def from_env(cls) -> "EchoSettings":
        base_dir = Path(os.getenv("ECHO_BASE_DIR", "~/.echo")).expanduser()
        return cls(
            base_dir=base_dir,
            host=os.getenv("ECHO_HOST", "0.0.0.0"),
            port=int(os.getenv("ECHO_PORT", "9010")),
            collection=os.getenv("ECHO_COLLECTION", "echo_vectors"),
            qdrant_url=os.getenv("ECHO_QDRANT_URL"),
            qdrant_api_key=os.getenv("ECHO_QDRANT_API_KEY"),
            embed_model=os.getenv("ECHO_EMBED_MODEL", "BAAI/bge-small-en-v1.5"),
        )


class UpsertDocument(BaseModel):
    text: str = Field(..., min_length=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    doc_id: Optional[str] = None


class UpsertRequest(BaseModel):
    documents: List[UpsertDocument]


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)


class EchoVectorStore:
    def __init__(self, settings: EchoSettings) -> None:
        self.settings = settings
        self.settings.base_dir.mkdir(parents=True, exist_ok=True)
        self.embedding = TextEmbedding(self.settings.embed_model)
        self.client = self._init_qdrant()
        self._ensure_collection()

    def _init_qdrant(self) -> QdrantClient:
        if self.settings.qdrant_url:
            return QdrantClient(
                url=self.settings.qdrant_url,
                api_key=self.settings.qdrant_api_key,
            )
        qdrant_path = self.settings.base_dir / "qdrant"
        qdrant_path.mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=str(qdrant_path))

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return [vector.tolist() for vector in self.embedding.embed(texts)]

    def _ensure_collection(self) -> None:
        try:
            if self.client.collection_exists(self.settings.collection):
                return
        except Exception as exc:  # pragma: no cover
            logger.warning("Collection existence check failed: %s", exc)

        sample_vector = self._embed(["echo-init"])[0]
        self.client.create_collection(
            collection_name=self.settings.collection,
            vectors_config=qdrant_models.VectorParams(
                size=len(sample_vector),
                distance=qdrant_models.Distance.COSINE,
            ),
        )

    def upsert(self, documents: List[UpsertDocument]) -> int:
        texts = [doc.text for doc in documents]
        vectors = self._embed(texts)
        points = []
        for doc, vector in zip(documents, vectors):
            payload = {"text": doc.text, **doc.metadata}
            point_id = doc.doc_id or str(uuid.uuid4())
            points.append(
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )
        self.client.upsert(self.settings.collection, points=points)
        return len(points)

    def query(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        vector = self._embed([query])[0]
        results = self.client.search(
            collection_name=self.settings.collection,
            query_vector=vector,
            limit=top_k,
        )
        response = []
        for hit in results:
            payload = hit.payload or {}
            response.append(
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "text": payload.get("text", ""),
                    "metadata": {k: v for k, v in payload.items() if k != "text"},
                }
            )
        return response


settings = EchoSettings.from_env()
store = EchoVectorStore(settings)

app = FastAPI(title="ECHO Vector Server", version="0.1.0")


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "collection": settings.collection,
        "model": settings.embed_model,
        "qdrant_url": settings.qdrant_url or "local",
    }


@app.post("/upsert")
def upsert(request: UpsertRequest) -> Dict[str, Any]:
    if not request.documents:
        raise HTTPException(status_code=400, detail="No documents provided.")
    try:
        count = store.upsert(request.documents)
        return {"success": True, "count": count}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/query")
def query(request: QueryRequest) -> Dict[str, Any]:
    try:
        results = store.query(request.query, request.top_k)
        return {"success": True, "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
