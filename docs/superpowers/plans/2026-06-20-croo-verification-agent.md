# CROO Verification Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a paid CAP agent that verifies claims, judges deliverables, and attests on-chain facts, returning signed verdicts backed by GenLayer consensus.

**Architecture:** A chain-agnostic `verifier_core` package (evidence adapters + Verifier interface + attestation) wrapped by a thin CROO/CAP provider adapter. The core is built and tested offline with injected dependencies; the live CROO and GenLayer pieces wrap it.

**Tech Stack:** Python 3.10+, `croo-sdk`, `web3`, `eth-account`, `httpx`, `pytest`, `python-dotenv`, GenLayer (`genlayer-py` + GenLayer Studio for the contract).

---

## File structure

```
croo-verify/
  verifier_core/
    __init__.py
    types.py            # VerifyRequest, Verdict, Attestation, VerifyResult
    attest.py           # result hash + signature + proof embedding
    pipeline.py         # validate, route by kind, gather evidence, verify, attest
    evidence/
      __init__.py
      web.py            # web evidence for `claim` (injected fetcher)
      onchain.py        # RPC reads for `onchain` (injected client)
    verifiers/
      __init__.py
      base.py           # Verifier protocol
      local_llm.py      # single-model fallback (injected LLM callable)
      genlayer.py       # GenLayer consensus verifier
  adapters/
    __init__.py
    croo.py             # CAP provider loop, wires verifier_core
  contracts/
    verifier.py         # GenLayer intelligent contract
  clients/
    verify_client.py    # 2-line drop-in for other teams
    requester_demo.py   # our own requester, settles a real USDC order
  satellites/
    research_agent.py   # consumer agent (fact-checks via verifier)
    content_agent.py    # consumer agent (attests claims)
  tests/                # mirrors module paths
  README.md
  LICENSE               # MIT
  pyproject.toml
  .env.example
```

Boundary rule: nothing under `verifier_core/` imports `croo` or any chain SDK. Chain code lives in `adapters/` and `clients/`. This is what lets Casper reuse the core later.

---

## Phase 0 - Setup

### Task 0: Repo scaffolding

**Files:**
- Create: `pyproject.toml`, `.env.example`, `LICENSE`, `README.md` (stub), `verifier_core/__init__.py`, `tests/__init__.py`, `pytest.ini`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "croo-verify"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "croo-sdk",
  "web3>=6",
  "eth-account>=0.10",
  "httpx>=0.27",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `.env.example`**

```
CROO_API_URL=https://api.croo.network
CROO_WS_URL=wss://api.croo.network/ws
CROO_SDK_KEY=croo_sk_...
WALLET_PRIVATE_KEY=0x...
GENLAYER_RPC_URL=
GENLAYER_VERIFIER_ADDRESS=
ONCHAIN_RPC_URL=
```

- [ ] **Step 3: Create `LICENSE`** (MIT, year 2026, holder "Kenny").

- [ ] **Step 4: Create empty `verifier_core/__init__.py` and `tests/__init__.py`.**

- [ ] **Step 5: Install dev env**

Run: `cd ~/Documents/croo-verify && python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"`
Expected: installs without error. If `croo-sdk` fails to resolve, note it and continue (it is only needed from Phase 2).

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Scaffold croo-verify: deps, license, env example"
```

---

## Phase 1 - verifier_core (offline, TDD)

### Task 1: Core types

**Files:**
- Create: `verifier_core/types.py`
- Test: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_types.py
from verifier_core.types import VerifyRequest, Verdict, Attestation, VerifyResult

def test_verify_request_from_json_valid():
    req = VerifyRequest.from_json('{"kind": "claim", "statement": "the sky is blue"}')
    assert req.kind == "claim"
    assert req.fields["statement"] == "the sky is blue"

def test_verify_request_rejects_unknown_kind():
    try:
        VerifyRequest.from_json('{"kind": "banana"}')
        assert False, "should have raised"
    except ValueError as e:
        assert "kind" in str(e)

def test_verify_result_to_json_roundtrip():
    att = Attestation(result_hash="0xabc", method="local_llm", signature="0xsig")
    res = VerifyResult(verdict="supported", confidence=0.9, reasoning="because",
                       evidence=["src1"], attestation=att)
    import json
    parsed = json.loads(res.to_json())
    assert parsed["verdict"] == "supported"
    assert parsed["attestation"]["method"] == "local_llm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_types.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `verifier_core/types.py`**

```python
import json
from dataclasses import dataclass, field, asdict

VALID_KINDS = {"claim", "deliverable", "onchain"}

@dataclass
class VerifyRequest:
    kind: str
    fields: dict

    @classmethod
    def from_json(cls, raw: str) -> "VerifyRequest":
        data = json.loads(raw)
        kind = data.get("kind")
        if kind not in VALID_KINDS:
            raise ValueError(f"unknown kind: {kind!r}")
        fields = {k: v for k, v in data.items() if k != "kind"}
        return cls(kind=kind, fields=fields)

@dataclass
class Attestation:
    result_hash: str
    method: str
    signature: str
    genlayer_tx: str | None = None
    onchain_proof: dict | None = None

@dataclass
class Verdict:
    verdict: str
    confidence: float
    reasoning: str
    evidence: list = field(default_factory=list)

@dataclass
class VerifyResult:
    verdict: str
    confidence: float
    reasoning: str
    evidence: list
    attestation: Attestation

    def to_json(self) -> str:
        return json.dumps(asdict(self))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_types.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add verifier_core/types.py tests/test_types.py
git commit -m "Add core types for verify requests, verdicts, attestations"
```

### Task 2: Attestation (hash + sign)

**Files:**
- Create: `verifier_core/attest.py`
- Test: `tests/test_attest.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_attest.py
from verifier_core.attest import build_attestation, canonical_hash
from verifier_core.types import Verdict
from eth_account import Account

def test_canonical_hash_is_stable():
    v = Verdict(verdict="supported", confidence=0.9, reasoning="x", evidence=["a"])
    assert canonical_hash(v) == canonical_hash(v)
    assert canonical_hash(v).startswith("0x")

def test_signature_recovers_to_signer():
    acct = Account.create()
    v = Verdict(verdict="supported", confidence=0.9, reasoning="x", evidence=["a"])
    att = build_attestation(v, method="local_llm", private_key=acct.key.hex())
    from eth_account.messages import encode_defunct
    msg = encode_defunct(hexstr=att.result_hash)
    recovered = Account.recover_message(msg, signature=att.signature)
    assert recovered.lower() == acct.address.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_attest.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `verifier_core/attest.py`**

```python
import json
import hashlib
from eth_account import Account
from eth_account.messages import encode_defunct
from .types import Verdict, Attestation

def canonical_hash(v: Verdict) -> str:
    payload = json.dumps(
        {"verdict": v.verdict, "confidence": v.confidence,
         "reasoning": v.reasoning, "evidence": v.evidence},
        sort_keys=True, separators=(",", ":"),
    )
    return "0x" + hashlib.sha256(payload.encode()).hexdigest()

def build_attestation(v: Verdict, method: str, private_key: str,
                      genlayer_tx: str | None = None,
                      onchain_proof: dict | None = None) -> Attestation:
    result_hash = canonical_hash(v)
    signed = Account.sign_message(encode_defunct(hexstr=result_hash),
                                  private_key=private_key)
    return Attestation(result_hash=result_hash, method=method,
                       signature=signed.signature.hex(),
                       genlayer_tx=genlayer_tx, onchain_proof=onchain_proof)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_attest.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add verifier_core/attest.py tests/test_attest.py
git commit -m "Add attestation: canonical hash + signature recoverable to signer"
```

### Task 3: Verifier interface + local_llm fallback

**Files:**
- Create: `verifier_core/verifiers/__init__.py`, `verifier_core/verifiers/base.py`, `verifier_core/verifiers/local_llm.py`
- Test: `tests/test_local_llm.py`

- [ ] **Step 1: Write the failing test** (inject the LLM call so the test is offline and deterministic)

```python
# tests/test_local_llm.py
from verifier_core.verifiers.local_llm import LocalLLMVerifier

def fake_llm(prompt: str) -> str:
    return '{"verdict": "supported", "confidence": 0.8, "reasoning": "matches evidence"}'

def test_local_llm_parses_verdict():
    v = LocalLLMVerifier(llm=fake_llm)
    out = v.verify("claim", {"statement": "x", "evidence": ["a", "b"]})
    assert out.verdict == "supported"
    assert out.confidence == 0.8
    assert out.evidence == ["a", "b"]

def test_local_llm_bad_json_returns_inconclusive():
    v = LocalLLMVerifier(llm=lambda p: "not json")
    out = v.verify("claim", {"statement": "x", "evidence": []})
    assert out.verdict == "inconclusive"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_local_llm.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `base.py`**

```python
# verifier_core/verifiers/base.py
from typing import Protocol
from ..types import Verdict

class Verifier(Protocol):
    def verify(self, kind: str, payload: dict) -> Verdict: ...
```

- [ ] **Step 4: Implement `local_llm.py`**

```python
# verifier_core/verifiers/local_llm.py
import json
from ..types import Verdict

PROMPT = """You are a strict verifier. Given a {kind} and evidence, decide the verdict.
Respond ONLY with JSON: {{"verdict": "...", "confidence": 0.0-1.0, "reasoning": "..."}}.
For claim: verdict in [supported, refuted, inconclusive].
For deliverable: verdict in [pass, fail, inconclusive].
Input: {payload}"""

class LocalLLMVerifier:
    def __init__(self, llm):
        self.llm = llm  # callable: prompt -> str

    def verify(self, kind: str, payload: dict) -> Verdict:
        evidence = payload.get("evidence", [])
        raw = self.llm(PROMPT.format(kind=kind, payload=json.dumps(payload)))
        try:
            data = json.loads(raw)
            return Verdict(verdict=data["verdict"],
                           confidence=float(data.get("confidence", 0.5)),
                           reasoning=data.get("reasoning", ""),
                           evidence=evidence)
        except Exception:
            return Verdict(verdict="inconclusive", confidence=0.0,
                           reasoning="verifier returned unparseable output",
                           evidence=evidence)
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/test_local_llm.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add verifier_core/verifiers/ tests/test_local_llm.py
git commit -m "Add Verifier interface and local_llm fallback with safe parsing"
```

### Task 4: Web evidence adapter

**Files:**
- Create: `verifier_core/evidence/__init__.py`, `verifier_core/evidence/web.py`
- Test: `tests/test_evidence_web.py`

- [ ] **Step 1: Write the failing test** (inject the fetcher)

```python
# tests/test_evidence_web.py
from verifier_core.evidence.web import gather_web_evidence

def fake_search(query):
    return [{"url": "https://a.com", "snippet": "blue sky confirmed"}]

def test_gather_returns_evidence_items():
    ev = gather_web_evidence("is the sky blue", search=fake_search)
    assert ev[0]["url"] == "https://a.com"
    assert "blue" in ev[0]["snippet"]

def test_gather_handles_search_failure():
    def boom(q): raise RuntimeError("network down")
    ev = gather_web_evidence("x", search=boom)
    assert ev == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_evidence_web.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `web.py`**

```python
# verifier_core/evidence/web.py
def gather_web_evidence(query: str, search) -> list:
    """search: callable(query)->list[{"url","snippet"}]. Never raises."""
    try:
        return list(search(query))
    except Exception:
        return []
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_evidence_web.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add verifier_core/evidence/__init__.py verifier_core/evidence/web.py tests/test_evidence_web.py
git commit -m "Add web evidence adapter (fails closed to empty list)"
```

### Task 5: On-chain evidence adapter

**Files:**
- Create: `verifier_core/evidence/onchain.py`
- Test: `tests/test_evidence_onchain.py`

- [ ] **Step 1: Write the failing test** (inject the chain reader)

```python
# tests/test_evidence_onchain.py
from verifier_core.evidence.onchain import check_onchain_fact

class FakeChain:
    def get_balance(self, addr): return 5_000_000  # 5 USDC (6 decimals)
    def tx_exists(self, h): return True
    def block_number(self): return 123

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
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_evidence_onchain.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `onchain.py`**

```python
# verifier_core/evidence/onchain.py
def check_onchain_fact(payload: dict, chain) -> dict:
    """chain provides get_balance/tx_exists/block_number. Returns a proof dict."""
    block = chain.block_number()
    check = payload.get("check")
    try:
        if check == "balance_gte":
            ok = chain.get_balance(payload["address"]) >= payload["min"]
            return {"result": bool(ok), "block": block}
        if check == "tx_exists":
            return {"result": bool(chain.tx_exists(payload["hash"])), "block": block}
        return {"result": False, "block": block, "reason": f"unsupported check: {check!r}"}
    except Exception as e:
        return {"result": False, "block": block, "reason": f"read failed: {e}"}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_evidence_onchain.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add verifier_core/evidence/onchain.py tests/test_evidence_onchain.py
git commit -m "Add on-chain evidence adapter for balance and tx checks"
```

### Task 6: Pipeline (routing + orchestration)

**Files:**
- Create: `verifier_core/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
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
    assert out.attestation.signature.startswith("0x") or out.attestation.signature

def test_onchain_path_is_deterministic_no_verifier():
    class FakeChain:
        def block_number(self): return 1
        def tx_exists(self, h): return True
    out = run_pipeline('{"kind": "onchain", "check": "tx_exists", "hash": "0x1"}',
                       verifier=StubVerifier(), private_key=PK,
                       search=None, chain=FakeChain())
    assert out.verdict in ("true", "false")
    assert out.attestation.method == "onchain"

def test_invalid_input_returns_invalid_verdict():
    out = run_pipeline('not json at all', verifier=StubVerifier(),
                       private_key=PK, search=None, chain=None)
    assert out.verdict == "invalid_input"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `pipeline.py`**

```python
# verifier_core/pipeline.py
from .types import VerifyRequest, Verdict, VerifyResult
from .attest import build_attestation
from .evidence.web import gather_web_evidence
from .evidence.onchain import check_onchain_fact

def _result(v: Verdict, method, private_key, **proof) -> VerifyResult:
    att = build_attestation(v, method=method, private_key=private_key, **proof)
    return VerifyResult(verdict=v.verdict, confidence=v.confidence,
                        reasoning=v.reasoning, evidence=v.evidence, attestation=att)

def run_pipeline(requirements_json, verifier, private_key, search, chain) -> VerifyResult:
    try:
        req = VerifyRequest.from_json(requirements_json)
    except Exception as e:
        v = Verdict(verdict="invalid_input", confidence=0.0,
                    reasoning=f"bad requirements: {e}", evidence=[])
        return _result(v, "local_llm", private_key)

    if req.kind == "onchain":
        proof = check_onchain_fact(req.fields, chain=chain)
        v = Verdict(verdict="true" if proof.get("result") else "false",
                    confidence=1.0 if "reason" not in proof else 0.0,
                    reasoning=proof.get("reason", "on-chain read"),
                    evidence=[proof])
        return _result(v, "onchain", private_key, onchain_proof=proof)

    if req.kind == "claim":
        statement = req.fields.get("statement", "")
        req.fields["evidence"] = gather_web_evidence(statement, search=search)

    # claim or deliverable -> verifier decides
    try:
        v = verifier.verify(req.kind, req.fields)
        method = getattr(verifier, "method_name", "local_llm")
    except Exception as e:
        v = Verdict(verdict="inconclusive", confidence=0.0,
                    reasoning=f"verifier error: {e}", evidence=req.fields.get("evidence", []))
        method = "local_llm"
    return _result(v, method, private_key,
                   genlayer_tx=getattr(v, "genlayer_tx", None))
```

Note: `Verdict` has no `genlayer_tx` attr by default, so `getattr(..., None)` returns None for the local path; the GenLayer verifier (Task 11) attaches it.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run the full core suite**

Run: `pytest tests/ -v`
Expected: all green. This proves the brain works offline, end to end.

- [ ] **Step 6: Commit**

```bash
git add verifier_core/pipeline.py tests/test_pipeline.py
git commit -m "Add pipeline: route by kind, gather evidence, verify, attest"
```

---

## Phase 2 - Verify the real SDK, then the CROO adapter

### Task 7: Probe the real croo-sdk API (no guessing)

**Files:**
- Create: `docs/sdk-notes.md`

- [ ] **Step 1: Install and inspect**

Run:
```bash
. .venv/bin/activate
pip install croo-sdk
python -c "import croo, inspect; print([n for n in dir(croo) if not n.startswith('_')])"
python -c "from croo import AgentClient; import inspect; print(inspect.signature(AgentClient.__init__)); print([m for m in dir(AgentClient) if not m.startswith('_')])"
```

- [ ] **Step 2: Record findings**

Write `docs/sdk-notes.md` with the exact class name, constructor signature, the real method names for `connect_websocket`, `accept_negotiation`, `deliver_order`, `negotiate_order`, `pay_order`, `get_delivery`, the real `EventType` member names, and the `DeliverOrderRequest` / `DeliverableType` shapes. The README suggests these names; this step confirms them against the installed package.

- [ ] **Step 3: Commit**

```bash
git add docs/sdk-notes.md && git commit -m "Record verified croo-sdk API surface"
```

### Task 8: CROO provider adapter

**Files:**
- Create: `adapters/__init__.py`, `adapters/croo.py`

Build against `docs/sdk-notes.md`. The skeleton below matches the README; reconcile any name differences with the probe before running.

- [ ] **Step 1: Implement `adapters/croo.py`**

```python
# adapters/croo.py
import os, asyncio
from croo import AgentClient, Config, EventType, DeliverableType, DeliverOrderRequest
from web3 import Web3
from verifier_core.pipeline import run_pipeline
from verifier_core.verifiers.local_llm import LocalLLMVerifier

def build_client() -> AgentClient:
    return AgentClient(Config(base_url=os.environ["CROO_API_URL"],
                              ws_url=os.environ["CROO_WS_URL"]),
                       os.environ["CROO_SDK_KEY"])

def make_search():
    # real web search wired here (httpx to a search API); kept injectable
    def search(query):
        return []  # replace with real provider in Task 12 hardening
    return search

def make_chain():
    w3 = Web3(Web3.HTTPProvider(os.environ["ONCHAIN_RPC_URL"]))
    class Chain:
        def block_number(self): return w3.eth.block_number
        def tx_exists(self, h): return w3.eth.get_transaction(h) is not None
        def get_balance(self, addr): return w3.eth.get_balance(Web3.to_checksum_address(addr))
    return Chain()

async def main():
    client = build_client()
    pk = os.environ["WALLET_PRIVATE_KEY"]
    verifier = LocalLLMVerifier(llm=...)  # real LLM call wired here
    search, chain = make_search(), make_chain()
    delivered = set()  # idempotency

    stream = await client.connect_websocket()

    def on_negotiation(e):
        asyncio.create_task(client.accept_negotiation(e.negotiation_id))

    def on_paid(e):
        async def handle():
            if e.order_id in delivered:
                return
            delivered.add(e.order_id)
            result = run_pipeline(e.requirements, verifier=verifier,
                                  private_key=pk, search=search, chain=chain)
            await client.deliver_order(e.order_id, DeliverOrderRequest(
                deliverable_type=DeliverableType.TEXT,
                deliverable_text=result.to_json()))
        asyncio.create_task(handle())

    stream.on(EventType.NEGOTIATION_CREATED, on_negotiation)
    stream.on(EventType.ORDER_PAID, on_paid)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Dashboard setup (manual, one time)**

Sign up at agent.croo.network, create the agent, register the service (name "verify.croo", price a few cents USDC, deliverable type Text, input = requirements JSON), issue the SDK key, and deposit USDC to the agent AA wallet. Put the SDK key and service id into `.env`.

- [ ] **Step 3: Smoke run**

Run: `python adapters/croo.py` and confirm it connects to the websocket without error. Stop with Ctrl-C.

- [ ] **Step 4: Commit**

```bash
git add adapters/ && git commit -m "Add CROO provider adapter wiring verifier_core into CAP"
```

### Task 9: Requester demo (settle a real USDC order)

**Files:**
- Create: `clients/requester_demo.py`

- [ ] **Step 1: Implement the requester** (based on the python-sdk requester flow; reconcile with `docs/sdk-notes.md`)

```python
# clients/requester_demo.py
import os, asyncio
from croo import AgentClient, Config, NegotiateOrderRequest

async def main():
    client = AgentClient(Config(base_url=os.environ["CROO_API_URL"],
                                ws_url=os.environ["CROO_WS_URL"]),
                         os.environ["CROO_SDK_KEY"])
    neg = await client.negotiate_order(NegotiateOrderRequest(
        service_id=os.environ["CROO_TARGET_SERVICE_ID"],
        requirements='{"kind": "claim", "statement": "USDC is a stablecoin"}'))
    order_id = neg.order.order_id
    await client.pay_order(order_id)
    delivery = await client.get_delivery(order_id)
    print(delivery.deliverable_text)

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Run the end-to-end settlement**

Run the provider (`python adapters/croo.py`) in one terminal and `python clients/requester_demo.py` in another. Expected: an order is created, paid in USDC, and the delivery prints a signed verdict JSON. This is the qualifying real settlement.

- [ ] **Step 3: Commit**

```bash
git add clients/requester_demo.py && git commit -m "Add requester demo that settles a real USDC verification order"
```

---

## Phase 3 - GenLayer-backed verifier

### Task 10: GenLayer verifier contract

**Files:**
- Create: `contracts/verifier.py`

Use the `genlayer-dev:write-contract` and `genlayer-dev:direct-tests` skills for this task.

- [ ] **Step 1:** Write an intelligent contract with a method `verify(kind: str, payload: str) -> str` that asks the validators (LLM consensus) to return the strict JSON verdict, using an equivalence principle so validators agree on the structured result. Pin a concrete GenVM runner version hash (never `latest`/`test`).

- [ ] **Step 2:** Write direct-mode tests that call `verify` with a clear claim and assert the parsed verdict.

Run: per the `genlayer-dev:direct-tests` skill.
Expected: PASS.

- [ ] **Step 3:** Deploy to GenLayer testnet, record the contract address in `.env` as `GENLAYER_VERIFIER_ADDRESS`.

- [ ] **Step 4: Commit**

```bash
git add contracts/verifier.py && git commit -m "Add GenLayer verifier contract with LLM-consensus verdicts"
```

### Task 11: GenLayer verifier client + wire as default

**Files:**
- Create: `verifier_core/verifiers/genlayer.py`
- Test: `tests/test_genlayer_verifier.py`
- Modify: `adapters/croo.py` (use GenLayer with local_llm fallback)

- [ ] **Step 1: Write the failing test** (inject the contract caller)

```python
# tests/test_genlayer_verifier.py
from verifier_core.verifiers.genlayer import GenLayerVerifier

def fake_call(kind, payload):
    return ('{"verdict": "supported", "confidence": 0.95, "reasoning": "consensus"}',
            "0xGENLAYERTX")

def test_genlayer_verifier_attaches_tx():
    v = GenLayerVerifier(call=fake_call)
    out = v.verify("claim", {"statement": "x", "evidence": []})
    assert out.verdict == "supported"
    assert out.genlayer_tx == "0xGENLAYERTX"

def test_genlayer_failure_raises_for_fallback():
    def boom(k, p): raise RuntimeError("testnet down")
    v = GenLayerVerifier(call=boom)
    try:
        v.verify("claim", {"statement": "x"})
        assert False
    except RuntimeError:
        pass
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_genlayer_verifier.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `genlayer.py`**

```python
# verifier_core/verifiers/genlayer.py
import json
from ..types import Verdict

class GenLayerVerifier:
    method_name = "genlayer"

    def __init__(self, call):
        self.call = call  # callable(kind, payload_json)->(result_json, tx_hash)

    def verify(self, kind: str, payload: dict) -> Verdict:
        raw, tx = self.call(kind, json.dumps(payload))
        data = json.loads(raw)
        v = Verdict(verdict=data["verdict"],
                    confidence=float(data.get("confidence", 0.5)),
                    reasoning=data.get("reasoning", ""),
                    evidence=payload.get("evidence", []))
        v.genlayer_tx = tx  # attached for the pipeline to embed
        return v
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_genlayer_verifier.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Wire fallback into the adapter.** In `adapters/croo.py`, build a wrapper that tries `GenLayerVerifier` first and falls back to `LocalLLMVerifier` on any exception:

```python
class VerifierWithFallback:
    def __init__(self, primary, fallback):
        self.primary, self.fallback = primary, fallback
    def verify(self, kind, payload):
        try:
            v = self.primary.verify(kind, payload)
            self.method_name = "genlayer"
            return v
        except Exception:
            self.method_name = "local_llm"
            return self.fallback.verify(kind, payload)
```

- [ ] **Step 6: Commit**

```bash
git add verifier_core/verifiers/genlayer.py tests/test_genlayer_verifier.py adapters/croo.py
git commit -m "Add GenLayer verifier with local_llm fallback"
```

---

## Phase 4 - Composability: integration kit, satellites, adoption

### Task 12: Integration kit (drop-in client) + README integration section

**Files:**
- Create: `clients/verify_client.py`
- Modify: `README.md`

- [ ] **Step 1: Implement a 2-line drop-in** other teams can copy:

```python
# clients/verify_client.py
import os, asyncio
from croo import AgentClient, Config, NegotiateOrderRequest

async def verify(requirements: str, service_id: str | None = None) -> str:
    client = AgentClient(Config(base_url=os.environ["CROO_API_URL"],
                                ws_url=os.environ["CROO_WS_URL"]),
                         os.environ["CROO_SDK_KEY"])
    neg = await client.negotiate_order(NegotiateOrderRequest(
        service_id=service_id or os.environ["CROO_VERIFY_SERVICE_ID"],
        requirements=requirements))
    await client.pay_order(neg.order.order_id)
    return (await client.get_delivery(neg.order.order_id)).deliverable_text
```

- [ ] **Step 2: Write the README integration section** with the public service id, the requirements schema for each kind, and an example response. Include the exact SDK methods used (this is a mandatory submission field).

- [ ] **Step 3: Commit**

```bash
git add clients/verify_client.py README.md
git commit -m "Add drop-in verify client and README integration guide"
```

### Task 13: Satellite consumer agents

**Files:**
- Create: `satellites/research_agent.py`, `satellites/content_agent.py`

- [ ] **Step 1:** `research_agent.py` answers a research question and calls `verify_client.verify('{"kind":"claim",...}')` on its key facts before returning, embedding the attestation. Register it as its own agent (own wallet) in the dashboard.

- [ ] **Step 2:** `content_agent.py` drafts a short post and calls the verifier to attest its claims before "publishing". Register as its own agent.

- [ ] **Step 3:** Run each against the live verifier so real cross-agent orders settle (these create genuine A2A edges for the composability score).

- [ ] **Step 4: Commit**

```bash
git add satellites/ && git commit -m "Add research and content satellite agents that consume the verifier"
```

### Task 14: Adoption push (drive real external orders)

**Files:**
- Create: `docs/adoption.md`

- [ ] **Step 1:** Write `docs/adoption.md`: the pitch for other CROO hackathon teams ("attest your agent's output in 2 lines"), the list of teams/people contacted, and a running tally toward the targets: 10+ orders, 5+ unique buyer wallets, 3+ counterparty agents.

- [ ] **Step 2:** Post the pitch in the CROO Discord / hackathon channel. Keep the price low so trying it is cheap. Track who integrates.

- [ ] **Step 3:** Check the CROO Agent Store / order data periodically and update the tally until targets are met.

- [ ] **Step 4: Commit** the adoption log as it grows.

---

## Phase 5 - Submission

### Task 15: README, demo, and file the BUIDL

- [ ] **Step 1:** Finish `README.md`: what it is, setup steps, env vars, the SDK methods used, integration notes, and the GenLayer backing explained.
- [ ] **Step 2:** Record a demo under 5 minutes: a requester pays, the verifier returns a signed verdict, show the GenLayer tx as proof, show a satellite agent and one external order in the CROO order data.
- [ ] **Step 3:** Push the repo public on GitHub (MIT license already present).
- [ ] **Step 4:** Confirm the agent is listed on the CROO Agent Store.
- [ ] **Step 5:** File the BUIDL on DoraHacks with every field complete and the repo + demo links.
- [ ] **Step 6: Commit** any final docs.

---

## Self-review notes

- Spec coverage: claim/deliverable/onchain (Tasks 4-6, 11), GenLayer backing (10-11), attestation (2), reliability/fallback/idempotency (3, 6, 8, 11), integration kit + satellites + adoption for the A2A targets (12-14), all five mandatory submission items (8 listing, 9 settlement, 0 license, 12/15 README+methods, 15 BUIDL). Casper reuse is preserved by the `verifier_core` boundary (no chain imports), no Casper task included on purpose.
- Live-service caveat: Tasks 8, 9, 10, 11 touch the real CROO API and GenLayer testnet. Their code matches the published READMEs; Task 7 verifies the exact API names first so the adapter code is reconciled before running, rather than trusting a paraphrase.
