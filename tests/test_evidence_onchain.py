from verifier_core.evidence.onchain import check_onchain_fact


class FakeChain:
    def get_balance(self, addr):
        return 5_000_000  # 5 USDC (6 decimals)

    def tx_exists(self, h):
        return True

    def block_number(self):
        return 123


def test_balance_check_true():
    out = check_onchain_fact({"check": "balance_gte", "address": "0x1",
                              "min": 1_000_000}, chain=FakeChain())
    assert out["result"] is True
    assert out["block"] == 123


def test_tx_check_true():
    out = check_onchain_fact({"check": "tx_exists", "hash": "0xabc"},
                             chain=FakeChain())
    assert out["result"] is True


def test_unknown_check_is_false_with_reason():
    out = check_onchain_fact({"check": "nope"}, chain=FakeChain())
    assert out["result"] is False
    assert "unsupported" in out["reason"]
