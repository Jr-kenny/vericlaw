"""Requester that settles a real USDC order against VeriClaw.

Flow (see docs/sdk-notes.md): negotiate_order returns a Negotiation; the Order is
not created until the provider accepts, so we listen for ORDER_CREATED to learn
the order id, then pay_order, then poll get_delivery.

Run the provider (python -m adapters.croo) first, then this in another terminal.
Set CROO_TARGET_SERVICE_ID to the VeriClaw service id. Optionally set
REQUESTER_SDK_KEY to act as a separate agent (recommended, avoids self-trade);
otherwise it reuses CROO_SDK_KEY.
"""
import asyncio
import os

from croo import AgentClient, Config, EventType, NegotiateOrderRequest


def build_requester() -> AgentClient:
    sdk_key = os.environ.get("REQUESTER_SDK_KEY") or os.environ["CROO_SDK_KEY"]
    return AgentClient(Config(base_url=os.environ["CROO_API_URL"],
                              ws_url=os.environ["CROO_WS_URL"]), sdk_key)


async def main():
    client = build_requester()
    order_ready: asyncio.Future = asyncio.get_event_loop().create_future()

    stream = await client.connect_websocket()

    def on_order_created(e):
        if not order_ready.done():
            order_ready.set_result(e.order_id)

    stream.on(EventType.ORDER_CREATED, on_order_created)

    requirements = '{"kind": "claim", "statement": "USDC is a dollar-backed stablecoin"}'
    neg = await client.negotiate_order(NegotiateOrderRequest(
        service_id=os.environ["CROO_TARGET_SERVICE_ID"],
        requirements=requirements))
    print(f"negotiation {neg.negotiation_id} sent, waiting for the provider to accept...")

    order_id = await asyncio.wait_for(order_ready, timeout=120)
    print(f"order {order_id} created, paying...")
    await client.pay_order(order_id)

    for _ in range(60):
        delivery = await client.get_delivery(order_id)
        if delivery and delivery.deliverable_text:
            print("--- signed verdict ---")
            print(delivery.deliverable_text)
            break
        await asyncio.sleep(2)
    else:
        print("no delivery within the wait window")

    await stream.close()
    await client.close()


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(main())
