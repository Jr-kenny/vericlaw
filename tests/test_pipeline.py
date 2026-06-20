from eth_account import Account
from verifier_core.pipeline import run_pipeline
from verifier_core.types import Verdict


class StubVerifier:
    def verify(self, kind, payload):
        return Verdict(verdict="supported", confidence=0.9,
                       reasoning="stub", evidence=payload.get("evidence", []))


PK = Account.create().key.hex()


def test_claim_path_signs_result():
    out = run_pipeline('{"kind": "claim", "statement": "sky blue"}',
                       verifier=StubVerifier(), private_key=PK,
                       search=lambda q: [{"url": "u", "snippet": "s"}],
                       chain=None)
    assert out.verdict == "supported"
    assert out.attestation.signature


def test_onchain_path_is_deterministic_no_verifier():
    class FakeChain:
        def block_number(self):
            return 1

        def tx_exists(self, h):
            return True

    out = run_pipeline('{"kind": "onchain", "check": "tx_exists", "hash": "0x1"}',
                       verifier=StubVerifier(), private_key=PK,
                       search=None, chain=FakeChain())
    assert out.verdict in ("true", "false")
    assert out.attestation.method == "onchain"


def test_invalid_input_returns_invalid_verdict():
    out = run_pipeline('not json at all', verifier=StubVerifier(),
                       private_key=PK, search=None, chain=None)
    assert out.verdict == "invalid_input"
