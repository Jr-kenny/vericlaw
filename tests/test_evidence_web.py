from verifier_core.evidence.web import gather_web_evidence


def fake_search(query):
    return [{"url": "https://a.com", "snippet": "blue sky confirmed"}]


def test_gather_returns_evidence_items():
    ev = gather_web_evidence("is the sky blue", search=fake_search)
    assert ev[0]["url"] == "https://a.com"
    assert "blue" in ev[0]["snippet"]


def test_gather_handles_search_failure():
    def boom(q):
        raise RuntimeError("network down")
    ev = gather_web_evidence("x", search=boom)
    assert ev == []
