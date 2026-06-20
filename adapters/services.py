"""VeriClaw multi-service routing.

Each CROO service maps to a GenLayer contract + method. The provider looks up the
incoming order's service_id, runs the matching contract, signs the result, and
delivers it. Service ids are set in .env once the services are registered in the
CROO dashboard.
"""
import json
import os

from adapters.genlayer_call import call_contract
from verifier_core.attest import hash_body, sign_hash

_WRAPPER_KEYS = ("text", "message", "input", "query", "content",
                 "requirements", "prompt", "task")
_FIELD_NAMES = ("target", "chain", "event", "criteria", "deliverable", "sources")


def _sources(f: dict) -> str:
    s = f.get("sources", [])
    if isinstance(s, list):
        return "\n".join(str(x) for x in s) if s else "none"
    return str(s) if s else "none"


SERVICES = {
    "trust": {
        "id_env": "CROO_TRUST_SERVICE_ID",
        "addr_env": "GENLAYER_TRUST_ADDRESS",
        "method": "trust_check",
        "default_field": "target",
        "args": lambda f: [str(f.get("target", "")), str(f.get("chain", "") or "ethereum")],
        "build": lambda label, reason, ex: {
            "verdict": label, "reasoning": reason,
            "resolved_ca": ex[0] if len(ex) > 0 else "",
            "resolved_chain": ex[1] if len(ex) > 1 else "",
            "namesakes": int(ex[2]) if len(ex) > 2 and ex[2].isdigit() else 0,
        },
    },
    "resolution": {
        "id_env": "CROO_RESOLUTION_SERVICE_ID",
        "addr_env": "GENLAYER_RESOLUTION_ADDRESS",
        "method": "resolve",
        "default_field": "event",
        "args": lambda f: [str(f.get("event", "")), _sources(f)],
        "build": lambda label, reason, ex: {"outcome": label, "reasoning": reason},
    },
    "auditor": {
        "id_env": "CROO_AUDITOR_SERVICE_ID",
        "addr_env": "GENLAYER_AUDITOR_ADDRESS",
        "method": "audit",
        "default_field": "deliverable",
        "args": lambda f: [str(f.get("criteria", "")), str(f.get("deliverable", "")), _sources(f)],
        "build": lambda label, reason, ex: {"verdict": label, "reasoning": reason},
    },
}


def resolve_service_key(service_id: str):
    """Which service a CROO order belongs to, by matching its service_id to env."""
    if not service_id:
        return None
    for key, cfg in SERVICES.items():
        if os.environ.get(cfg["id_env"], "") == service_id:
            return key
    return None


def _fields(requirements: str, default_field: str) -> dict:
    """Parse requirements into a field dict, unwrapping buyer-agent envelopes."""
    try:
        data = json.loads(requirements)
    except Exception:
        return {default_field: str(requirements)}
    if isinstance(data, str):
        return {default_field: data}
    if not isinstance(data, dict):
        return {default_field: str(data)}
    if any(k in data for k in _FIELD_NAMES):
        return data
    for wk in _WRAPPER_KEYS:
        v = data.get(wk)
        if isinstance(v, str) and v.strip():
            return _fields(v, default_field)
    return data


def run_service(service_key: str, requirements: str, private_key: str) -> str:
    """Run one service end to end and return the signed deliverable JSON."""
    cfg = SERVICES[service_key]
    addr = os.environ[cfg["addr_env"]]
    fields = _fields(requirements, cfg["default_field"])
    label, reason, extras, tx = call_contract(addr, cfg["method"], cfg["args"](fields))
    body = cfg["build"](label, reason, extras)
    result_hash = hash_body(body)
    body["attestation"] = {
        "result_hash": result_hash, "method": "genlayer_consensus",
        "genlayer_tx": tx, "signature": sign_hash(result_hash, private_key),
    }
    return json.dumps(body)
