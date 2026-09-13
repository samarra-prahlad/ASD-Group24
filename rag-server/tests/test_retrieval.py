from retrieval import search


def test_search_returns_match_for_relevant_query():
    documents = [
        {"source": "policy.md", "text": "Late payment fee policy: a 5 percent fee applies after 30 days overdue"}
    ]
    result = search(documents, "What is the late payment fee policy")

    assert result["confidence"] in ("high", "medium")
    assert len(result["citations"]) == 1
    assert result["citations"][0]["source"] == "policy.md"


def test_search_returns_insufficient_for_unrelated_query():
    documents = [
        {"source": "policy.md", "text": "Late payment fee policy: a 5 percent fee applies after 30 days overdue"}
    ]
    result = search(documents, "What is the weather forecast for tomorrow")

    assert result["confidence"] == "insufficient"
    assert result["citations"] == []


def test_search_with_no_documents_returns_insufficient():
    result = search([], "anything")

    assert result["confidence"] == "insufficient"
    assert result["citations"] == []