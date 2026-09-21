import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import chromadb


EMBED_VECTOR_SIZE = 256

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
CORPUS_PATH = Path(__file__).parent / "corpus" / "corpus.jsonl"
CHUNK_SIZE_WORDS = 80
CHROMA_DIR = Path(__file__).parent / "chroma"
CHROMA_COLLECTION_NAME = "rag_corpus"


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        values = [0.0] * EMBED_VECTOR_SIZE
        tokens = (text or "").lower().split()
        if not tokens:
            vectors.append(values)
            continue
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i, byte in enumerate(digest):
                idx = i % EMBED_VECTOR_SIZE
                values[idx] += (byte / 255.0) - 0.5
        norm = sum(v * v for v in values) ** 0.5
        if norm > 0:
            values = [v / norm for v in values]
        vectors.append(values)
    return vectors


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE_WORDS) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]


def build_corpus() -> list[dict]:
    chunks = []
    if not KNOWLEDGE_DIR.exists():
        return chunks
    for feature_dir in sorted(KNOWLEDGE_DIR.iterdir()):
        if not feature_dir.is_dir():
            continue
        files = sorted(feature_dir.glob("*.md")) + sorted(feature_dir.glob("*.txt"))
        for file_path in files:
            source_id = f"{feature_dir.name}/{file_path.name}"
            text = file_path.read_text(encoding="utf-8")
            for i, block in enumerate(_chunk_text(text)):
                chunk_id = hashlib.sha256(f"{source_id}:{i}".encode("utf-8")).hexdigest()[:16]
                chunks.append({
                    "chunk_id": chunk_id,
                    "source_id": source_id,
                    "authority_tier": "tier_1",
                    "text": block,
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                })
    return chunks


def write_corpus(chunks: list[dict]) -> None:
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CORPUS_PATH, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")


def get_chroma_client():
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def refresh_corpus() -> dict:
    chunks = build_corpus()
    write_corpus(chunks)

    client = get_chroma_client()
    try:
        client.delete_collection(CHROMA_COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(CHROMA_COLLECTION_NAME)

    if chunks:
        texts = [c["text"] for c in chunks]
        embeddings = embed_texts(texts)
        ids = [c["chunk_id"] for c in chunks]
        metadatas = [
            {
                "source_id": c["source_id"],
                "authority_tier": c["authority_tier"],
                "indexed_at": c["indexed_at"],
            }
            for c in chunks
        ]
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)

    return {"status": "ok", "chunks_indexed": len(chunks)}


def _lexical_score(query_tokens: list[str], text: str) -> int:
    text_tokens = set(text.lower().split())
    return len(set(query_tokens) & text_tokens)


def lexical_fallback_retrieve(query: str, top_k: int = 5) -> list[dict]:
    if not CORPUS_PATH.exists():
        return []
    query_tokens = query.lower().split()
    scored = []
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            score = _lexical_score(query_tokens, chunk["text"])
            if score > 0:
                scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, chunk in scored[:top_k]:
        results.append({
            "chunk_id": chunk["chunk_id"],
            "source_id": chunk["source_id"],
            "authority_tier": chunk["authority_tier"],
            "text": chunk["text"],
            "score": float(score),
        })
    return results


def retrieve_context(query: str, top_k: int = 5) -> dict:
    client = get_chroma_client()
    try:
        collection = client.get_collection(CHROMA_COLLECTION_NAME)
        if collection.count() == 0:
            raise ValueError("empty collection")

        query_embedding = embed_texts([query])[0]
        raw = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
        )

        results = []
        ids = raw["ids"][0]
        docs = raw["documents"][0]
        metadatas = raw["metadatas"][0]
        distances = raw["distances"][0]
        for i in range(len(ids)):
            results.append({
                "chunk_id": ids[i],
                "source_id": metadatas[i]["source_id"],
                "authority_tier": metadatas[i]["authority_tier"],
                "text": docs[i],
                "score": float(1 - distances[i]) if distances[i] is not None else None,
            })
        return {"retrieval_mode": "vector", "results": results}
    except Exception:
        results = lexical_fallback_retrieve(query, top_k)
        return {"retrieval_mode": "lexical", "results": results}