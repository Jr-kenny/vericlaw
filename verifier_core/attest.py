import json
import hashlib
from eth_account import Account
from eth_account.messages import encode_defunct
from .types import Verdict, Attestation


def canonical_hash(v: Verdict) -> str:
    payload = json.dumps(
        {"verdict": v.verdict, "confidence": v.confidence,
         "reasoning": v.reasoning, "evidence": v.evidence},
        sort_keys=True, separators=(",", ":"),
    )
    return "0x" + hashlib.sha256(payload.encode()).hexdigest()


def build_attestation(v: Verdict, method: str, private_key: str,
                      genlayer_tx: str | None = None,
                      onchain_proof: dict | None = None) -> Attestation:
    result_hash = canonical_hash(v)
    signed = Account.sign_message(encode_defunct(hexstr=result_hash),
                                  private_key=private_key)
    return Attestation(result_hash=result_hash, method=method,
                       signature=signed.signature.hex(),
                       genlayer_tx=genlayer_tx, onchain_proof=onchain_proof)
