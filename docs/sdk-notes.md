# croo-sdk verified API surface

Probed from the installed `croo` package (Python). These are the real names, not
paraphrased from the README. Use these in `adapters/croo.py` and the clients.

## Client

```python
from croo import AgentClient, Config
client = AgentClient(Config(base_url=..., ws_url=..., rpc_url=""), sdk_key)
```

- `Config(base_url: str, ws_url: str = "", rpc_url: str = "")`
- `AgentClient(config: Config, sdk_key: str)`

## Methods (all async)

- `accept_negotiation(negotiation_id) -> AcceptNegotiationResult`  (has `.negotiation`, `.order`)
- `accept_negotiation_with_fund_address(...)`
- `reject_negotiation(...)`, `reject_order(...)`
- `negotiate_order(req: NegotiateOrderRequest) -> Negotiation`
- `pay_order(order_id) -> PayOrderResult`
- `deliver_order(order_id, req: DeliverOrderRequest) -> DeliverOrderResult`
- `get_delivery(order_id) -> Delivery`
- `get_order(order_id) -> Order`
- `get_negotiation(negotiation_id) -> Negotiation`
- `list_orders(...)`, `list_negotiations(...)`
- `connect_websocket() -> EventStream`
- `close()`

## Requests

- `NegotiateOrderRequest(service_id, requirements="", metadata="", requester_agent_id="", fund_amount="", fund_token="")`
- `DeliverOrderRequest(deliverable_type, deliverable_schema="", deliverable_text="")`

## Enums

- `EventType`: NEGOTIATION_CREATED, NEGOTIATION_EXPIRED, NEGOTIATION_REJECTED,
  ORDER_CREATED, ORDER_PAID, ORDER_COMPLETED, ORDER_EXPIRED, ORDER_REJECTED
- `DeliverableType`: TEXT, SCHEMA

## EventStream

`stream = await client.connect_websocket()` then `stream.on(EventType.X, cb)`.
Also has `on_any`, `connect`, `close`, `err`.

## Event object fields

`Event` has: `type, raw, negotiation_id, order_id, requester_agent_id,
provider_agent_id, service_id, status, reason`.

## IMPORTANT corrections to the plan (found by probing)

1. The `ORDER_PAID` event does NOT carry the `requirements` text. Only
   `order_id` (and ids). The verification input lives on the Negotiation
   (`Negotiation.requirements`). So the provider's on-paid handler must resolve
   it:
   - `order = await client.get_order(e.order_id)` -> `order.negotiation_id`
   - `neg = await client.get_negotiation(order.negotiation_id)` -> `neg.requirements`
   Or stash `requirements` keyed by `negotiation_id` when `NEGOTIATION_CREATED`
   fires (we already call `get_negotiation` there), then map order->negotiation
   on paid. Task 8 must use one of these, not `e.requirements`.

2. The requester flow: `negotiate_order()` returns a `Negotiation`. The Order is
   not created until the provider accepts. So `requester_demo` cannot read
   `neg.order.order_id` directly. It must either listen for the `ORDER_CREATED`
   event (carries `order_id`) and then `pay_order`, or poll
   `get_negotiation`/`list_orders` until the order exists. Task 9 must follow
   this, not assume an immediate order id.

3. `Order` carries the useful audit fields for the demo: `price`,
   `payment_token`, `pay_tx_hash`, `clear_tx_hash`, `sla_deadline`,
   `requester_wallet_address`. Good material for the demo video proof.
