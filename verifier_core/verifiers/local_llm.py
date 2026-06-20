import json
from ..types import Verdict

PROMPT = """You are a strict verifier. Given a {kind} and evidence, decide the verdict.
Respond ONLY with JSON: {{"verdict": "...", "confidence": 0.0-1.0, "reasoning": "..."}}.
For claim: verdict in [supported, refuted, inconclusive].
For deliverable: verdict in [pass, fail, inconclusive].
Input: {payload}"""


class LocalLLMVerifier:
    def __init__(self, llm):
        self.llm = llm  # callable: prompt -> str

    def verify(self, kind: str, payload: dict) -> Verdict:
        evidence = payload.get("evidence", [])
        raw = self.llm(PROMPT.format(kind=kind, payload=json.dumps(payload)))
        try:
            data = json.loads(raw)
            return Verdict(verdict=data["verdict"],
                           confidence=float(data.get("confidence", 0.5)),
                           reasoning=data.get("reasoning", ""),
                           evidence=evidence)
        except Exception:
            return Verdict(verdict="inconclusive", confidence=0.0,
                           reasoning="verifier returned unparseable output",
                           evidence=evidence)
