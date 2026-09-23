from rag_pipeline import confidence_from_results


def _result(authority_tier="tier_1", score=0.9):
    return {
        "chunk_id": "abc",
        "source_id": "billing/x.md",
        "authority_tier": authority_tier,
        "text": "some text",
        "score": score,
    }


def test_confidence_high_with_strong_tier1_matches():
    results = [_result(score=0.9), _result(score=0.85)]
    assert confidence_from_results(results) == "High"


def test_confidence_medium_with_moderate_matches():
    results = [_result(score=0.55)]
    assert confidence_from_results(results) == "Medium"


def test_confidence_low_with_weak_matches():
    results = [_result(score=0.2)]
    assert confidence_from_results(results) == "Low"


def test_confidence_insufficient_with_no_results():
    assert confidence_from_results([]) == "Insufficient"


def test_confidence_lower_tier_reduces_confidence():
    tier1_results = [_result(authority_tier="tier_1", score=0.9)]
    tier3_results = [_result(authority_tier="tier_3", score=0.9)]
    assert confidence_from_results(tier1_results) == "High"
    assert confidence_from_results(tier3_results) != "High"