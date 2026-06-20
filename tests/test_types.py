from verifier_core.types import VerifyRequest, Verdict, Attestation, VerifyResult


def test_verify_request_from_json_valid():
    req = VerifyRequest.from_json('{"kind": "claim", "statement": "the sky is blue"}')
    assert req.kind == "claim"
    assert req.fields["statement"] == "the sky is blue"


def test_verify_request_rejects_unknown_kind():
    try:
        VerifyRequest.from_json('{"kind": "banana"}')
        assert False, "should have raised"
    except ValueError as e:
        assert "kind" in str(e)


def test_verify_result_to_json_roundtrip():
    att = Attestation(result_hash="0xabc", method="local_llm", signature="0xsig")
    res = VerifyResult(verdict="supported", confidence=0.9, reasoning="because",
                       evidence=["src1"], attestation=att)
    import json
    parsed = json.loads(res.to_json())
    assert parsed["verdict"] == "supported"
    assert parsed["attestation"]["method"] == "local_llm"
