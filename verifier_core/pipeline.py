from .types import VerifyRequest, Verdict, VerifyResult
from .attest import build_attestation
from .evidence.web import gather_web_evidence
from .evidence.onchain import check_onchain_fact


def _result(v: Verdict, method, private_key, **proof) -> VerifyResult:
    att = build_attestation(v, method=method, private_key=private_key, **proof)
    return VerifyResult(verdict=v.verdict, confidence=v.confidence,
                        reasoning=v.reasoning, evidence=v.evidence, attestation=att)


def run_pipeline(requirements_json, verifier, private_key, search, chain) -> VerifyResult:
    try:
        req = VerifyRequest.from_json(requirements_json)
    except Exception as e:
        v = Verdict(verdict="invalid_input", confidence=0.0,
                    reasoning=f"bad requirements: {e}", evidence=[])
        return _result(v, "local_llm", private_key)

    if req.kind == "onchain":
        proof = check_onchain_fact(req.fields, chain=chain)
        v = Verdict(verdict="true" if proof.get("result") else "false",
                    confidence=1.0 if "reason" not in proof else 0.0,
                    reasoning=proof.get("reason", "on-chain read"),
                    evidence=[proof])
        return _result(v, "onchain", private_key, onchain_proof=proof)

    if req.kind == "claim":
        statement = req.fields.get("statement", "")
        req.fields["evidence"] = gather_web_evidence(statement, search=search)

    # claim or deliverable -> verifier decides
    try:
        v = verifier.verify(req.kind, req.fields)
        method = getattr(verifier, "method_name", "local_llm")
    except Exception as e:
        v = Verdict(verdict="inconclusive", confidence=0.0,
                    reasoning=f"verifier error: {e}",
                    evidence=req.fields.get("evidence", []))
        method = "local_llm"
    return _result(v, method, private_key,
                   genlayer_tx=getattr(v, "genlayer_tx", None))
