"""CROO/CAP provider adapter. Wires verifier_core into the live protocol.

The provider listens for negotiations, accepts them, and on payment runs the
verification pipeline and delivers a signed verdict. The ORDER_PAID event only
carries an order id, so the requirements (the actual question) are resolved by
walking order -> negotiation. See docs/sdk-notes.md.
"""
import asyncio
import os

from croo import (AgentClient, Config, EventType, DeliverableType,
                  DeliverOrderRequest)

from verifier_core.pipeline import run_pipeline


async def resolve_requirements(client, order_id: str) -> str:
    """The paid event has no requirements; walk order -> negotiation to get them."""
    order = await client.get_order(order_id)
    neg = await client.get_negotiation(order.negotiation_id)
    return neg.requirements


async def handle_paid(client, order_id: str, *, verifier, private_key,
                      search, chain, delivered: set) -> bool:
    """Run the pipeline and deliver once. Returns False if already delivered."""
    if order_id in delivered:
        return False
    delivered.add(order_id)
    requirements = await resolve_requirements(client, order_id)
    result = run_pipeline(requirements, verifier=verifier, private_key=private_key,
                          search=search, chain=chain)
    await client.deliver_order(order_id, DeliverOrderRequest(
        deliverable_type=DeliverableType.TEXT,
        deliverable_text=result.to_json()))
    return True


def build_client() -> AgentClient:
    return AgentClient(Config(base_url=os.environ["CROO_API_URL"],
                              ws_url=os.environ["CROO_WS_URL"]),
                       os.environ["CROO_SDK_KEY"])


class VerifierWithFallback:
    """GenLayer consensus first; fall back to the local verifier on any failure
    (timeout, testnet hiccup) so a CROO order never misses its SLA."""

    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self.method_name = "genlayer"

    def verify(self, kind, payload):
        try:
            v = self.primary.verify(kind, payload)
            self.method_name = "genlayer"
            return v
        except Exception:
            if self.fallback is None:
                raise
            self.method_name = "local_llm"
            return self.fallback.verify(kind, payload)


def make_verifier():
    """GenLayer consensus verifier as primary; Claude as fallback if a key is set.
    If GenLayer fails and there is no Claude key, the pipeline returns an
    `inconclusive` verdict rather than hanging the order."""
    from verifier_core.verifiers.genlayer import GenLayerVerifier
    from adapters.genlayer_call import make_genlayer_call
    primary = GenLayerVerifier(call=make_genlayer_call())
    fallback = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        from verifier_core.verifiers.local_llm import LocalLLMVerifier
        from adapters.llm import make_claude_llm
        fallback = LocalLLMVerifier(llm=make_claude_llm())
    return VerifierWithFallback(primary, fallback)


def make_search():
    """Web search used as claim evidence. Returns [] until a provider is wired."""
    def search(query):
        return []
    return search


def make_chain():
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(os.environ["ONCHAIN_RPC_URL"]))

    class Chain:
        def block_number(self):
            return w3.eth.block_number

        def tx_exists(self, h):
            try:
                return w3.eth.get_transaction(h) is not None
            except Exception:
                return False

        def get_balance(self, addr):
            return w3.eth.get_balance(Web3.to_checksum_address(addr))

    return Chain()


async def main():
    client = build_client()
    pk = os.environ["WALLET_PRIVATE_KEY"]
    verifier = make_verifier()
    search = make_search()
    chain = make_chain() if os.environ.get("ONCHAIN_RPC_URL") else None
    delivered: set = set()

    stream = await client.connect_websocket()

    def on_negotiation(e):
        asyncio.create_task(client.accept_negotiation(e.negotiation_id))

    def on_paid(e):
        asyncio.create_task(handle_paid(client, e.order_id, verifier=verifier,
                                        private_key=pk, search=search, chain=chain,
                                        delivered=delivered))

    stream.on(EventType.NEGOTIATION_CREATED, on_negotiation)
    stream.on(EventType.ORDER_PAID, on_paid)
    print("VeriClaw provider running. Waiting for negotiations...")
    await asyncio.Event().wait()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())
