from rag_instance import mcp
from rag_pipeline import refresh_corpus, retrieve_context, answer_question

AVAILABLE_TOOLS = ["refresh_corpus", "retrieve_context", "answer_question"]


@mcp.tool(name="refresh_corpus")
def refresh_corpus_tool() -> dict:
    """Rebuild the corpus from knowledge files and repopulate the vector index."""
    return refresh_corpus()


@mcp.tool(name="retrieve_context")
def retrieve_context_tool(query: str, top_k: int = 5) -> dict:
    """Retrieve the top-k most relevant knowledge chunks for a query."""
    return retrieve_context(query, top_k)


@mcp.tool(name="answer_question")
def answer_question_tool(query: str, top_k: int = 5) -> dict:
    """Answer a question using retrieval-augmented generation, with citations and confidence."""
    return answer_question(query, top_k)


if __name__ == "__main__":
    print("Starting Group24 Shared RAG Server...")
    print("Server status: RUNNING")
    print("Available tools:")
    for tool in AVAILABLE_TOOLS:
        print(f"- {tool}")
    mcp.run(transport="streamable-http")