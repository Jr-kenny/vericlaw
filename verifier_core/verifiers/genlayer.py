import json
from ..types import Verdict


class GenLayerVerifier:
    """Verifier backed by the deployed GenLayer intelligent contract.

    `call` is injected: callable(kind, payload_json) -> (result_json, tx_hash).
    The real implementation writes to the contract and reads the leader's
    verdict; tests pass a stub. Any failure propagates so the caller can fall
    back to the local verifier.
    """
    method_name = "genlayer"

    def __init__(self, call):
        self.call = call

    def verify(self, kind: str, payload: dict) -> Verdict:
        raw, tx = self.call(kind, json.dumps(payload))
        data = json.loads(raw)
        v = Verdict(verdict=data["verdict"],
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", ""),
                    evidence=payload.get("evidence", []))
        v.genlayer_tx = tx
        return v
