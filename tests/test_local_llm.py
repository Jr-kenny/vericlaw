from verifier_core.verifiers.local_llm import LocalLLMVerifier


def fake_llm(prompt: str) -> str:
    return '{"verdict": "supported", "confidence": 0.8, "reasoning": "matches evidence"}'


def test_local_llm_parses_verdict():
    v = LocalLLMVerifier(llm=fake_llm)
    out = v.verify("claim", {"statement": "x", "evidence": ["a", "b"]})
    assert out.verdict == "supported"
    assert out.confidence == 0.8
    assert out.evidence == ["a", "b"]


def test_local_llm_bad_json_returns_inconclusive():
    v = LocalLLMVerifier(llm=lambda p: "not json")
    out = v.verify("claim", {"statement": "x", "evidence": []})
    assert out.verdict == "inconclusive"
