import json
from eth_account import Account
from verifier_core.types import Verdict
from adapters.croo import resolve_requirements, handle_paid


PK = Account.create().key.hex()


class FakeOrder:
    def __init__(self, negotiation_id):
        self.negotiation_id = negotiation_id


class FakeNegotiation:
    def __init__(self, requirements):
        self.requirements = requirements


class FakeClient:
    def __init__(self, requirements):
        self._requirements = requirements
        self.delivered = []

    async def get_order(self, order_id):
        return FakeOrder(negotiation_id="neg-" + order_id)

    async def get_negotiation(self, negotiation_id):
        return FakeNegotiation(self._requirements)

    async def deliver_order(self, order_id, req):
        self.delivered.append((order_id, req))
        return None


class StubVerifier:
    def verify(self, kind, payload):
        return Verdict(verdict="supported", confidence=0.9, reasoning="stub",
                       evidence=payload.get("evidence", []))


async def test_resolve_requirements_walks_order_to_negotiation():
    client = FakeClient('{"kind": "claim", "statement": "x"}')
    req = await resolve_requirements(client, "order-1")
    assert req == '{"kind": "claim", "statement": "x"}'


async def test_handle_paid_delivers_signed_verdict_once():
    client = FakeClient('{"kind": "claim", "statement": "x"}')
    seen = set()
    did = await handle_paid(client, "order-1", verifier=StubVerifier(),
                            private_key=PK, search=lambda q: [], chain=None,
                            delivered=seen)
    assert did is True
    assert len(client.delivered) == 1
    order_id, req = client.delivered[0]
    body = json.loads(req.deliverable_text)
    assert body["verdict"] == "supported"
    assert body["attestation"]["signature"]


async def test_handle_paid_is_idempotent():
    client = FakeClient('{"kind": "claim", "statement": "x"}')
    seen = set()
    await handle_paid(client, "order-1", verifier=StubVerifier(), private_key=PK,
                      search=lambda q: [], chain=None, delivered=seen)
    did_again = await handle_paid(client, "order-1", verifier=StubVerifier(),
                                  private_key=PK, search=lambda q: [], chain=None,
                                  delivered=seen)
    assert did_again is False
    assert len(client.delivered) == 1
