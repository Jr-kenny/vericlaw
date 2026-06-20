from verifier_core.attest import build_attestation, canonical_hash
from verifier_core.types import Verdict
from eth_account import Account


def test_canonical_hash_is_stable():
    v = Verdict(verdict="supported", confidence=0.9, reasoning="x", evidence=["a"])
    assert canonical_hash(v) == canonical_hash(v)
    assert canonical_hash(v).startswith("0x")


def test_signature_recovers_to_signer():
    acct = Account.create()
    v = Verdict(verdict="supported", confidence=0.9, reasoning="x", evidence=["a"])
    att = build_attestation(v, method="local_llm", private_key=acct.key.hex())
    from eth_account.messages import encode_defunct
    msg = encode_defunct(hexstr=att.result_hash)
    recovered = Account.recover_message(msg, signature=att.signature)
    assert recovered.lower() == acct.address.lower()
