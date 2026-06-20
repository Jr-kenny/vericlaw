from typing import Protocol
from ..types import Verdict


class Verifier(Protocol):
    def verify(self, kind: str, payload: dict) -> Verdict: ...
