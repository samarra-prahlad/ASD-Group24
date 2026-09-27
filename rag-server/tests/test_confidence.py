"""
Tests for confidence_from_results in rag_pipeline.py.

The hash-based embedding used by embed_texts() is not a real semantic
embedding - cosine similarity scores come out low and inconsistently
signed regardless of actual topical relevance (confirmed empirically:
an on-topic billing query scored -0.25, an off-topic "capital of France"
query scored -0.21). So confidence can't be derived from the vector score
alone; it must also check for literal, non-stopword token overlap with
the top retrieved chunk, since that reliably tells relevant queries apart
from irrelevant ones in this corpus. An earlier version of this check
used raw (unfiltered) token overlap, which incorrectly let "what is the
capital of France" pass because it shared stopwords ("of", "the", "is")
with an unrelated billing chunk - confirmed directly against the real
corpus, see test_stopword_only_overlap_is_insufficient below.

Run with:
    pytest tests/test_confidence.py -v
"""

from rag_pipeline import confidence_from_results


def _result(text, score, authority_tier="tier_1"):
    return {
        "chunk_id": "abc123",
        "source_id": "billing/some_doc.md",
        "authority_tier": authority_tier,
        "text": text,
        "score": score,
    }


class TestConfidenceFromResults:

    def test_no_results_is_insufficient(self):
        assert confidence_from_results([], "any query") == "Insufficient"

    def test_zero_token_overlap_is_insufficient_even_with_decent_score(self):
        results = [_result("invoice patient status pending payment", 0.6)]
        assert confidence_from_results(results, "what is the capital of France") == "Insufficient"

    def test_stopword_only_overlap_is_insufficient(self):
        # Regression test: "what is the capital of France" only shared
        # stopwords ("of", "the", "is") with an unrelated billing chunk,
        # which wrongly passed the old overlap check. Stopwords must not
        # count as meaningful overlap.
        results = [_result(
            "patient owed amount total_amount minus insurance_covered_amount rounded decimal places",
            -0.21,
        )]
        assert confidence_from_results(results, "what is the capital of france") == "Insufficient"

    def test_some_token_overlap_with_high_score_is_high(self):
        results = [_result("invoice status pending payment owed", 0.8)]
        assert confidence_from_results(results, "what does pending invoice status mean") == "High"

    def test_some_token_overlap_with_medium_score_is_medium(self):
        results = [_result("invoice status pending payment owed", 0.5)]
        assert confidence_from_results(results, "what does pending invoice status mean") == "Medium"

    def test_some_token_overlap_with_low_score_is_low(self):
        results = [_result("invoice status pending payment owed", 0.2)]
        assert confidence_from_results(results, "what does pending invoice status mean") == "Low"

    def test_negative_score_with_overlap_is_still_low_not_insufficient(self):
        results = [_result("invoice status pending", -0.25)]
        assert confidence_from_results(results, "what does pending invoice status mean") == "Low"

    def test_authority_tier_weighting_still_applies(self):
        results = [_result("invoice status pending", 0.9, authority_tier="tier_3")]
        # 0.9 * 0.4 (tier_3 weight) = 0.36 -> Low, not High
        assert confidence_from_results(results, "invoice status pending") == "Low"