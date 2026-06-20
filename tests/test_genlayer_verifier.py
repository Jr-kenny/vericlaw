from verifier_core.verifiers.genlayer import GenLayerVerifier


def fake_call(kind, content, sources):
    return ('{"verdict": "supported", "reasoning": "consensus"}', "0xGENLAYERTX")


def test_genlayer_verifier_attaches_tx():
    v = GenLayerVerifier(call=fake_call)
    out = v.verify("claim", {"statement": "x", "sources": []})
    assert out.verdict == "supported"
    assert out.genlayer_tx == "0xGENLAYERTX"


def test_genlayer_verifier_passes_content_and_sources():
    seen = {}

    def capture(kind, content, sources):
        seen["content"] = content
        seen["sources"] = sources
        return ('{"verdict": "pass", "reasoning": "ok"}', "0xTX")

    v = GenLayerVerifier(call=capture)
    v.verify("deliverable", {"criteria": "must compile", "output": "it compiles",
                             "sources": ["https://a.com", "https://b.com"]})
    assert "must compile" in seen["content"]
    assert "it compiles" in seen["content"]
    assert seen["sources"] == "https://a.com\nhttps://b.com"


def test_genlayer_failure_raises_for_fallback():
    def boom(k, c, s):
        raise RuntimeError("testnet down")
    v = GenLayerVerifier(call=boom)
    try:
        v.verify("claim", {"statement": "x"})
        assert False, "should have raised"
    except RuntimeError:
        pass
