# RAG Server — Tool Contracts

Shared, non-containerised RAG server. Runs locally on port 7001 (MCP/FastMCP transport) and 8001 (plain HTTP, for manual testing). Reached from feature backends via `http://host.docker.internal:7001/mcp` (inside containers) or directly at `http://localhost:7001/mcp` (host processes).

## Tools

### `refresh_corpus()`
Rebuilds the corpus from `knowledge/<feature>/*.md` files, chunks them (max 80 words/chunk), and repopulates the ChromaDB vector index.

**Input:** none
**Output:**
```json
{ "status": "ok", "chunks_indexed": 12 }
```

### `retrieve_context(query: str, top_k: int = 5)`
Returns the top-k most relevant knowledge chunks for a query, via vector search (with automatic lexical fallback if the vector index is empty/unavailable).

**Input:** `query` (string, required), `top_k` (int, default 5)
**Output:**
```json
{
  "retrieval_mode": "vector",
  "results": [
    {
      "chunk_id": "abc123",
      "source_id": "billing/late_fee.md",
      "authority_tier": "tier_1",
      "text": "...",
      "score": 0.87
    }
  ]
}
```

### `answer_question(query: str, top_k: int = 5)`
Retrieves context, classifies confidence, and generates a grounded answer via a local Ollama model, with citations back to source chunks.

**Input:** `query` (string, required), `top_k` (int, default 5)
**Output (ok):**
```json
{
  "status": "ok",
  "query": "what is the late fee",
  "answer": "Late payments incur a five percent fee after thirty days overdue.",
  "citations": [
    { "source_id": "billing/late_fee.md", "chunk_id": "abc123" }
  ],
  "confidence_category": "High",
  "retrieval_summary": { "retrieval_mode": "vector", "num_results": 1 }
}
```
**Output (insufficient context):**
```json
{
  "status": "insufficient_context",
  "query": "...",
  "answer": "There is not enough information in the knowledge base to answer this question.",
  "citations": [],
  "confidence_category": "Insufficient",
  "retrieval_summary": { "retrieval_mode": "lexical", "num_results": 0 }
}
```

## Confidence categories
Derived from authority-tier-weighted retrieval score of the top result:
- **High**: weighted score ≥ 0.75
- **Medium**: weighted score ≥ 0.45
- **Low**: weighted score < 0.45
- **Insufficient**: no results retrieved

## Audit logging
Every `answer_question` call is logged to `rag-audit.jsonl` with timestamp, query, status, retrieval mode, confidence category, and duration in ms. Not committed to git (generated artefact, in `.gitignore`).

## Safety/boundary notes
All three tools are read-only — no tool writes to any feature's data. `refresh_corpus` only rewrites the RAG server's own corpus/index files, never feature databases.