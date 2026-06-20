import json
from dataclasses import dataclass, field, asdict

VALID_KINDS = {"claim", "deliverable", "onchain"}

# Buyer agents often wrap the real payload in an envelope like {"text": "..."}.
# These keys are unwrapped when the top-level object has no `kind`.
WRAPPER_KEYS = ("text", "message", "input", "query", "content",
                "requirements", "prompt", "task")


@dataclass
class VerifyRequest:
    kind: str
    fields: dict

    @classmethod
    def from_json(cls, raw: str) -> "VerifyRequest":
        data = json.loads(raw)
        return cls._from_obj(data)

    @classmethod
    def _from_obj(cls, data) -> "VerifyRequest":
        # A bare string payload is treated as a claim to verify.
        if isinstance(data, str):
            return cls(kind="claim", fields={"statement": data})
        if not isinstance(data, dict):
            raise ValueError("unknown kind: None")

        kind = data.get("kind")
        if kind in VALID_KINDS:
            return cls(kind=kind, fields={k: v for k, v in data.items() if k != "kind"})
        if kind is not None:
            raise ValueError(f"unknown kind: {kind!r}")

        # No `kind` at top level: try to unwrap a known envelope field.
        for key in WRAPPER_KEYS:
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                try:
                    return cls._from_obj(json.loads(val))
                except (ValueError, TypeError):
                    return cls(kind="claim", fields={"statement": val})
        raise ValueError("unknown kind: None")


@dataclass
class Attestation:
    result_hash: str
    method: str
    signature: str
    genlayer_tx: str | None = None
    onchain_proof: dict | None = None


@dataclass
class Verdict:
    verdict: str
    confidence: float
    reasoning: str
    evidence: list = field(default_factory=list)


@dataclass
class VerifyResult:
    verdict: str
    confidence: float
    reasoning: str
    evidence: list
    attestation: Attestation

    def to_json(self) -> str:
        return json.dumps(asdict(self))
