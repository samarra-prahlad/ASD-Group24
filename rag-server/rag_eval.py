import json
from pathlib import Path

from rag_pipeline import retrieve_context

EVAL_SET_PATH = Path(__file__).parent / "eval" / "eval_queries.json"
METRICS_OUTPUT_PATH = Path(__file__).parent / "retrieval-metrics.md"


def load_eval_set() -> list[dict]:
    if not EVAL_SET_PATH.exists():
        return []
    with open(EVAL_SET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def precision_at_k(retrieved_source_ids: list[str], relevant_source_ids: list[str], k: int = 5) -> float:
    top_k = retrieved_source_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for s in top_k if s in relevant_source_ids)
    return hits / len(top_k)


def recall_at_k(retrieved_source_ids: list[str], relevant_source_ids: list[str], k: int = 5) -> float:
    if not relevant_source_ids:
        return 0.0
    top_k = retrieved_source_ids[:k]
    hits = sum(1 for s in relevant_source_ids if s in top_k)
    return hits / len(relevant_source_ids)


def run_eval(k: int = 5) -> dict:
    eval_set = load_eval_set()
    if not eval_set:
        return {"status": "no_eval_set", "cases": 0}

    precisions = []
    recalls = []
    per_query_results = []

    for case in eval_set:
        query = case["query"]
        relevant = case["relevant_source_ids"]

        retrieval = retrieve_context(query, top_k=k)
        retrieved_ids = [r["source_id"] for r in retrieval["results"]]

        p = precision_at_k(retrieved_ids, relevant, k)
        r = recall_at_k(retrieved_ids, relevant, k)

        precisions.append(p)
        recalls.append(r)
        per_query_results.append({
            "query": query,
            "precision_at_k": p,
            "recall_at_k": r,
            "retrieval_mode": retrieval["retrieval_mode"],
        })

    avg_precision = sum(precisions) / len(precisions)
    avg_recall = sum(recalls) / len(recalls)

    return {
        "status": "ok",
        "cases": len(eval_set),
        "k": k,
        "avg_precision_at_k": avg_precision,
        "avg_recall_at_k": avg_recall,
        "per_query": per_query_results,
    }


def write_metrics_report(results: dict) -> None:
    lines = ["# Retrieval Metrics\n"]
    if results["status"] == "no_eval_set":
        lines.append("No eval set found at `eval/eval_queries.json`. Add labelled queries to run this benchmark.\n")
    else:
        lines.append(f"Evaluated on {results['cases']} queries, k={results['k']}.\n")
        lines.append(f"- **Average Precision@{results['k']}**: {results['avg_precision_at_k']:.3f}")
        lines.append(f"- **Average Recall@{results['k']}**: {results['avg_recall_at_k']:.3f}\n")
        lines.append("| Query | Precision@k | Recall@k | Mode |")
        lines.append("|---|---|---|---|")
        for row in results["per_query"]:
            lines.append(f"| {row['query']} | {row['precision_at_k']:.2f} | {row['recall_at_k']:.2f} | {row['retrieval_mode']} |")

    METRICS_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    results = run_eval()
    write_metrics_report(results)
    print(f"Eval complete: {results['status']}. Report written to {METRICS_OUTPUT_PATH}")