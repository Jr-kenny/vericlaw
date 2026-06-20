# VeriClaw

A paid verification agent on the CROO Agent Protocol (CAP). Other agents hire it
to verify something and get back a **signed verdict they can trust**:

- `claim` - is this statement true, judged against source URLs the agent fetches itself
- `deliverable` - does this output meet the agreed acceptance criteria
- `onchain` - attest an on-chain fact (a tx happened, a balance, a contract)

The subjective verdicts (`claim`, `deliverable`) are decided by a **GenLayer
intelligent contract running multi-validator LLM consensus**. For claims with
source URLs, the contract fetches those pages itself during consensus, so the
whole check (go look, then decide) is verifiable and reproducible, not one
hidden model's opinion. Every reply is signed and carries the GenLayer
consensus transaction as proof.

## Hire it in two lines

VeriClaw service id: `e1bd03d6-a3ea-4f79-8640-3b85bff62ad3`

```python
from verify_client import verify  # clients/verify_client.py

verdict = await verify('{"kind":"claim","statement":"Ethereum supports smart contracts","sources":["https://en.wikipedia.org/wiki/Ethereum"]}')
print(verdict)
```

You need the standard CROO env vars (`CROO_API_URL`, `CROO_WS_URL`,
`CROO_SDK_KEY`) and a little USDC in your agent's AA wallet. Each call costs a
few cents.

## What you send (`requirements`)

A JSON object with a `kind`:

```jsonc
// claim: verify a statement (sources optional; fetched in-consensus)
{"kind":"claim","statement":"...","sources":["https://..."]}

// deliverable: judge an output against criteria
{"kind":"deliverable","criteria":"...","output":"...","sources":["https://..."]}

// onchain: attest an on-chain fact
{"kind":"onchain","check":"tx_exists","hash":"0x..."}
{"kind":"onchain","check":"balance_gte","address":"0x...","min":1000000}
```

## What you get back (`deliverable_text`)

```json
{
  "verdict": "supported",
  "confidence": 0.5,
  "reasoning": "Ethereum is a blockchain platform known for supporting smart contracts.",
  "evidence": ["https://en.wikipedia.org/wiki/Ethereum"],
  "attestation": {
    "result_hash": "0x...",
    "method": "genlayer",
    "genlayer_tx": "0x...",
    "signature": "0x..."
  }
}
```

`method` is `genlayer` when the verdict came from on-chain consensus,
`onchain` for deterministic chain reads, or `local_llm` if it fell back. The
`signature` is over `result_hash` and recovers to the agent's signing key, so a
verdict can't be tampered with after the fact.

## How it works

```
requester --(CAP order, USDC)--> VeriClaw provider
                                    -> verifier_core pipeline (route by kind)
                                    -> GenLayer contract (fetch sources + LLM consensus)
                                    -> sign the verdict, deliver, settle
```

- `verifier_core/` - chain-agnostic engine: request types, evidence adapters,
  the `Verifier` interface, attestation (hash + signature).
- `adapters/croo.py` - the CAP provider loop.
- `adapters/genlayer_call.py` - calls the deployed GenLayer verifier contract.
- `contracts/verifier.py` - the GenLayer intelligent contract (deployed on
  studionet at `0xe29e1eae338fFC6c422c0EB9C3e0A8391Dd439d0`).

If GenLayer is slow or unreachable, the agent retries once, then falls back to a
local model (if configured), and otherwise returns a safe `inconclusive` rather
than ever missing the order's SLA.

## CAP SDK methods used

Provider side: `connect_websocket`, `accept_negotiation`, `get_order`,
`get_negotiation`, `deliver_order` (with `DeliverableType.TEXT`).
Requester side: `negotiate_order`, `pay_order`, `get_delivery`.

## Run the provider

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in CROO_SDK_KEY, WALLET_PRIVATE_KEY, GENLAYER_* etc.
python -m adapters.croo
```

See `docs/superpowers/` for the design and plan, and `docs/sdk-notes.md` for the
verified CROO SDK API surface. MIT licensed.
