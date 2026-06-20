import json
import adapters.services as svc
from eth_account import Account

PK = Account.create().key.hex()


def test_fields_unwraps_text_envelope():
    raw = '{"text": "{\\"target\\":\\"PEPE\\",\\"chain\\":\\"ethereum\\"}"}'
    f = svc._fields(raw, "target")
    assert f["target"] == "PEPE"
    assert f["chain"] == "ethereum"


def test_fields_bare_string_uses_default_field():
    f = svc._fields('"0xabc"', "target")
    assert f["target"] == "0xabc"


def test_resolve_service_key_matches_env(monkeypatch):
    monkeypatch.setenv("CROO_TRUST_SERVICE_ID", "svc-trust-1")
    assert svc.resolve_service_key("svc-trust-1") == "trust"
    assert svc.resolve_service_key("nope") is None
    assert svc.resolve_service_key("") is None


def test_run_service_trust_builds_signed_body(monkeypatch):
    monkeypatch.setenv("GENLAYER_TRUST_ADDRESS", "0xcontract")

    def fake_call(addr, method, args, timeout=300):
        assert method == "trust_check"
        assert args[0] == "PEPE"
        return ("caution", "ok", ["0x6982", "ethereum", "2"], "0xTX")

    monkeypatch.setattr(svc, "call_contract", fake_call)
    out = json.loads(svc.run_service("trust", '{"target":"PEPE","chain":"ethereum"}', PK))
    assert out["verdict"] == "caution"
    assert out["resolved_ca"] == "0x6982"
    assert out["namesakes"] == 2
    assert out["attestation"]["genlayer_tx"] == "0xTX"
    assert out["attestation"]["signature"]


def test_run_service_resolution_shape(monkeypatch):
    monkeypatch.setenv("GENLAYER_RESOLUTION_ADDRESS", "0xres")

    def fake_call(addr, method, args, timeout=300):
        assert method == "resolve"
        return ("yes", "it happened", [], "0xTX2")

    monkeypatch.setattr(svc, "call_contract", fake_call)
    out = json.loads(svc.run_service("resolution", '{"event":"x"}', PK))
    assert out["outcome"] == "yes"
    assert out["attestation"]["genlayer_tx"] == "0xTX2"
