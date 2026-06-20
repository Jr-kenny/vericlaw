from verifier_core.verifiers.genlayer import GenLayerVerifier


def fake_call(kind, payload):
    return ('{"verdict": "supported", "confidence": 0.95, "reasoning": "consensus"}',
            "0xGENLAYERTX")


def test_genlayer_verifier_attaches_tx():
    v = GenLayerVerifier(call=fake_call)
    out = v.verify("claim", {"statement": "x", "evidence": []})
    assert out.verdict == "supported"
    assert out.genlayer_tx == "0xGENLAYERTX"


def test_genlayer_failure_raises_for_fallback():
    def boom(k, p):
        raise RuntimeError("testnet down")
    v = GenLayerVerifier(call=boom)
    try:
        v.verify("claim", {"statement": "x"})
        assert False, "should have raised"
    except RuntimeError:
        pass
