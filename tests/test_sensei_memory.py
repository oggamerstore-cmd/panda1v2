import json
from pathlib import Path

from app.memory import parse_sensei_jsonl, SenseiVectorMemory


def test_jsonl_parser_valid_and_invalid_lines(tmp_path):
    jsonl_path = tmp_path / "knowledge_injections.jsonl"
    lines = [
        "\n",
        "{bad json}\n",
        json.dumps({"id": "", "title": "No id"}) + "\n",
        json.dumps({"id": "1"}) + "\n",
        json.dumps({"id": "2", "title": "Alpha", "summary": "A", "tags": "x, y"}) + "\n",
        json.dumps({"id": "3", "summary": "Only summary", "tags": ["t1", "t2"]}) + "\n",
    ]
    jsonl_path.write_text("".join(lines), encoding="utf-8")

    docs = parse_sensei_jsonl(jsonl_path)

    assert len(docs) == 2
    assert docs[0]["injection_id"] == "2"
    assert docs[0]["tags"] == ["x", "y"]
    assert docs[1]["injection_id"] == "3"
    assert docs[1]["title"] == "Only summary"


def test_ingest_idempotent_skips_same_sha(tmp_path):
    def embedder(texts):
        return [[float("alpha" in text.lower()), 0.0] for text in texts]

    memory = SenseiVectorMemory(base_dir=tmp_path / "sensei", embedder=embedder)
    doc = {"injection_id": "a1", "title": "Alpha", "tags": [], "text": "alpha"}

    first = memory.ingest_docs([doc])
    assert first["inserted"] == 1
    assert first["total"] == 1

    second = memory.ingest_docs([doc])
    assert second["skipped"] == 1
    assert second["total"] == 1

    updated_doc = {"injection_id": "a1", "title": "Alpha", "tags": [], "text": "alpha updated"}
    third = memory.ingest_docs([updated_doc])
    assert third["updated"] == 1
    assert third["total"] == 1


def test_similarity_search_returns_topk(tmp_path):
    def embedder(texts):
        embeddings = []
        for text in texts:
            lower = text.lower()
            embeddings.append([float(lower.count("alpha")), float(lower.count("beta"))])
        return embeddings

    memory = SenseiVectorMemory(base_dir=tmp_path / "sensei", embedder=embedder)
    docs = [
        {"injection_id": "alpha1", "title": "Alpha Doc", "tags": [], "text": "alpha alpha"},
        {"injection_id": "beta1", "title": "Beta Doc", "tags": [], "text": "beta"},
        {"injection_id": "alpha2", "title": "Alpha Notes", "tags": [], "text": "alpha"},
    ]
    memory.ingest_docs(docs)

    results = memory.search("alpha", top_k=2)

    assert len(results) == 2
    assert results[0]["injection_id"] in {"alpha1", "alpha2"}
