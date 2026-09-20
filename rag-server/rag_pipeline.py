import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

EMBED_VECTOR_SIZE = 256

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
CORPUS_PATH = Path(__file__).parent / "corpus" / "corpus.jsonl"
CHUNK_SIZE_WORDS = 80


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