# VeriClaw - CROO Verification Agent - Design Spec

Date: 2026-06-20
Hackathon: CROO Agent Hackathon (DoraHacks). Submissions close 2026-07-12.
Track: Data & Verification.

## 1. What we are building

One paid agent on the CROO Agent Protocol (CAP) that other agents call to get
something verified. The caller pays a small amount of USDC, the agent does the
check, and returns a signed verdict.

One service, three kinds of check, one shared pipeline:

- `claim` - verify a real-world statement against live web evidence.
- `deliverable` - judge whether an output meets agreed acceptance criteria.
- `onchain` - attest an on-chain fact (a tx happened, a balance, a contract is
  verified, token metadata).

The subjective checks (`claim`, `deliverable`) are decided by a GenLayer
intelligent contract that runs multi-validator LLM consensus, and we return the
GenLayer transaction hash as proof. The `onchain` check is deterministic (a
direct RPC read with a block proof). Every reply carries an attestation: a
result hash, the method used, a GenLayer tx or block proof, and the agent's
signature.

## 2. Why this wins under the published judging criteria

Weights: Technical Execution 30%, A2A Composability 25%, Innovation 20%,
Usability & Real Adoption 15%, Presentation 10%.

- A verification agent is the rare agent other teams *want* to depend on
  ("fact-check / attest my output before I ship it"). That is the wedge for
  Composability (25%) and Adoption (15%).
- Three kinds give different consumer agents different reasons to call us, so we
  get diverse A2A edges instead of one repeated edge.
- Innovation (20%) answer to "would this be worse on a normal API marketplace?":
  yes. A normal marketplace returns a JSON blob you must trust. Ours returns a
  verdict backed by GenLayer multi-validator consensus, with an on-chain tx as
  proof, settled through escrow with reputation.
- Technical Execution (30%) has a bonus for 10+ real CAP orders. We reach that
  through real external adoption, not self-trade.

## 3. Reward-eligibility / anti-sybil targets

The rules flag (for review, not auto-DQ): fewer than 3 unique counterparty
agents, fewer than 5 unique buyer wallets, concentrated self-trade, and a random
10% human audit failure.

Targets baked into the plan:

- 10+ real CAP orders during the hackathon.
- 5+ unique external buyer wallets.
- 3+ unique counterparty agents.
- No concentrated self-trade pattern. Our own satellite agents demonstrate depth
  but are not the whole order graph; the buyer-wallet count is reached through
  genuine external users.

## 4. Architecture

Language: Python (`croo-sdk`). One language for the agent loop, web reads, RPC
reads, LLM calls, and the GenLayer client.

Components:

- `provider.py` - the CAP loop. Connect websocket, on `NEGOTIATION_CREATED` call
  `accept_negotiation`, on `ORDER_PAID` run the pipeline and `deliver_order`.
  Thin on purpose.
- `pipeline.py` - validate the requirements JSON, route by `kind`, gather
  evidence, call the verifier, build the attestation, return `deliverable_text`.
- `evidence/web.py` - gather web evidence for `claim`.
- `evidence/onchain.py` - RPC reads for `onchain`.
  (`deliverable` needs no gathering; the criteria and output are supplied.)
- `verifiers/genlayer.py` - call the deployed GenLayer contract (consensus).
- `verifiers/local_llm.py` - single-model fallback behind the same interface.
- `attest.py` - hash the result, sign it, embed the GenLayer tx or block proof.
- `contracts/verifier.py` - the GenLayer intelligent contract (adapted from
  prior verdict/resolution work), deployed to GenLayer testnet.
- Integration kit: `verify_client.py` (a 2-line drop-in for other teams), the
  requirements schema per kind, and example responses in the README.
- Satellite consumer agents (lightweight): a research agent that fact-checks via
  the verifier, a content agent that attests claims before publishing. Each has
  its own wallet. Used to show composability depth in the demo.

## 5. Call shape

Input (requester `requirements` JSON):

```json
{ "kind": "claim" | "deliverable" | "onchain", "...": "kind-specific fields" }
```

Output (`deliverable_text` JSON):

```json
{
  "verdict": "supported | refuted | inconclusive | pass | fail | true | false",
  "confidence": 0.0,
  "reasoning": "short explanation",
  "evidence": ["..."],
  "attestation": {
    "result_hash": "...",
    "method": "genlayer | local_llm | onchain",
    "genlayer_tx": "optional",
    "onchain_proof": "optional",
    "signature": "..."
  }
}
```

## 6. The Verifier interface

Both verifiers implement the same call: `verify(kind, payload) -> Verdict`.
`genlayer.py` is the default for `claim` and `deliverable`. `local_llm.py` is the
fallback. `onchain` does not use a verifier; it reads the chain and is its own
proof.

## 7. Reliability (this is escrow money)

Failing to deliver triggers a dispute and a loss, so every path must produce a
valid deliverable before the SLA expires.

- Malformed input -> return an `invalid_input` verdict, do not crash.
- Evidence fetch fails, or GenLayer is down -> fall back to `local_llm` and/or
  return `inconclusive`. Never leave the order hanging.
- `ORDER_PAID` handling is idempotent (same order delivered once).
- A per-order timeout sits inside the SLA window.

## 8. Build order (so the deadline is safe)

1. `claim` end-to-end: provider loop, pipeline, web evidence, local_llm verifier,
   attestation, and a real USDC settlement from our own requester. This alone
   satisfies the five mandatory requirements and earns the onboarding bounty.
2. Swap in the GenLayer verifier for `claim` and `deliverable`.
3. Add the `deliverable` kind.
4. Add the `onchain` kind.
5. Integration kit + satellite agents + adoption push to hit the A2A targets.
6. Demo video (under 5 min) + README + file the BUIDL on DoraHacks.

## 9. Mandatory submission checklist

- Listed on CROO Agent Store.
- Integrated with CAP, callable, settles on-chain.
- Public GitHub repo, MIT license.
- Demo video under 5 minutes.
- README: setup steps, SDK methods used, integration notes.
- BUIDL filed on DoraHacks with all fields.

## 10. Testing

- Unit: web evidence adapter (mocked), onchain adapter (mocked RPC), pipeline
  routing, attestation hash + signature.
- Verifier: interface tests with a stubbed GenLayer; direct-mode tests for the
  GenLayer contract.
- Integration: run the provider against CROO testnet with our requester, assert
  a real settled order and a valid delivery.

## 11. Reuse for other hackathons (Casper Agentic Buildathon)

The Casper Agentic Buildathon (DoraHacks, ~$150k, qualification round closes
2026-07-01) is a possible second home for this work. Casper pays agents through
x402 micropayments, not CAP, and is WebAssembly-native. So the payment/transport
layer differs, but the verification engine does not.

Decision: build the verification engine as a standalone, chain-agnostic package
with a hard boundary, and treat each chain as a thin adapter around it.

- `verifier_core/` - the engine: evidence adapters, the `Verifier` interface
  (GenLayer + local_llm), attestation. No CROO or Casper imports. Fully tested
  on its own.
- `adapters/croo.py` - the CAP provider loop (built now).
- `adapters/casper_x402.py` - an x402 adapter (later, only if we are ahead of
  schedule). Not in the CROO build.

Priority: CROO is the anchor and ships first and complete. Casper is a stretch
bolt-on, not a rewrite. Before submitting to both, confirm each event's rules on
related/double submissions, and note the earlier Casper deadline (2026-07-01).

## 12. Where it lives

`~/Documents/croo-verify`, its own git repo with its own public GitHub remote.
Not the reasoning folder.
