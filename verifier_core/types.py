import json
from dataclasses import dataclass, field, asdict

VALID_KINDS = {"claim", "deliverable", "onchain"}


@dataclass
class VerifyRequest:
    kind: str
    fields: dict

    @classmethod
    def from_json(cls, raw: str) -> "VerifyRequest":
        data = json.loads(raw)
        kind = data.get("kind")
        if kind not in VALID_KINDS:
            raise ValueError(f"unknown kind: {kind!r}")
        fields = {k: v for k, v in data.items() if k != "kind"}
        return cls(kind=kind, fields=fields)


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
