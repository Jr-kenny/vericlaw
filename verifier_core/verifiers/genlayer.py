import json
from ..types import Verdict


def _content_for(kind: str, payload: dict) -> str:
    if kind == "deliverable":
        return ("CRITERIA: " + str(payload.get("criteria", "")) + "\n"
                "OUTPUT: " + str(payload.get("output", "")))
    return str(payload.get("statement", payload.get("content", "")))


class GenLayerVerifier:
    """Verifier backed by the deployed GenLayer contract.

    `call` is injected: callable(kind, content, sources) -> (result_json, tx_hash).
    The contract fetches the source URLs itself during consensus, so evidence
    gathering is on-chain. Any failure propagates so the caller can fall back.
    """
    method_name = "genlayer"

    def __init__(self, call):
        self.call = call

    def verify(self, kind: str, payload: dict) -> Verdict:
        content = _content_for(kind, payload)
        sources = "\n".join(payload.get("sources", []) or [])
        raw, tx = self.call(kind, content, sources)
        data = json.loads(raw)
        v = Verdict(verdict=data["verdict"],
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", ""),
                    evidence=payload.get("sources", []) or [])
        v.genlayer_tx = tx
        return v
