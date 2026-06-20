"""Drop-in client for hiring VeriClaw from another agent.

Copy this file into your project and call `verify(...)`. It negotiates an order
with VeriClaw, pays the (few cents) USDC, and returns the signed verdict JSON.

    from verify_client import verify
    verdict = await verify('{"kind":"claim","statement":"...","sources":["https://..."]}')

Needs the standard CROO env vars (CROO_API_URL, CROO_WS_URL, CROO_SDK_KEY) and
your agent's AA wallet funded with a little USDC. The VeriClaw service id defaults
to VERICLAW_SERVICE_ID or the published id below.
"""
import asyncio
import os

from croo import AgentClient, Config, EventType, NegotiateOrderRequest

VERICLAW_SERVICE_ID = "e1bd03d6-a3ea-4f79-8640-3b85bff62ad3"


async def verify(requirements: str, service_id: str | None = None,
                 timeout: int = 180) -> str:
    """Hire VeriClaw and return its signed verdict JSON. `requirements` is the
    JSON described in the README (a {"kind": ...} object)."""
    sid = service_id or os.environ.get("VERICLAW_SERVICE_ID", VERICLAW_SERVICE_ID)
    client = AgentClient(Config(base_url=os.environ["CROO_API_URL"],
                                ws_url=os.environ["CROO_WS_URL"]),
                         os.environ["CROO_SDK_KEY"])
    order_ready: asyncio.Future = asyncio.get_event_loop().create_future()

    stream = await client.connect_websocket()

    def on_created(e):
        if not order_ready.done():
            order_ready.set_result(e.order_id)

    stream.on(EventType.ORDER_CREATED, on_created)
    try:
        await client.negotiate_order(NegotiateOrderRequest(
            service_id=sid, requirements=requirements))
        order_id = await asyncio.wait_for(order_ready, timeout=timeout)
        await client.pay_order(order_id)
        for _ in range(max(1, timeout // 3)):
            delivery = await client.get_delivery(order_id)
            if delivery and delivery.deliverable_text:
                return delivery.deliverable_text
            await asyncio.sleep(3)
        raise TimeoutError("VeriClaw did not deliver in time")
    finally:
        await stream.close()
        await client.close()
