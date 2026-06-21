"""Live call into the deployed GenLayer verifier contract.

Shells out to the authenticated `genlayer` CLI (network already set to studionet,
account unlocked) to run the contract's `verify(kind, payload)` method, and parses
the leader's verdict and the transaction hash from the output.

The payload is flattened to plain text first: the CLI types a `{...}` argument as a
dict, but the contract expects a `str`, so we pass `key: value | ...` instead.

Returns a `call(kind, payload_json) -> (result_json, tx_hash)` for GenLayerVerifier.
Any failure raises so the agent can fall back to the local verifier.
"""
import json
import os
import re
import subprocess

_VERDICT_RE = re.compile(r"VERDICT=([a-zA-Z_]+)\|([^\"]*)\"")
_TX_RE = re.compile(r"0x[0-9a-fA-F]{64}")


def _parse_cli_output(stdout: str):
    m = _VERDICT_RE.search(stdout)
    if not m:
        raise RuntimeError("could not parse GenLayer verdict from CLI output")
    label = m.group(1).strip().lower()
    reason = m.group(2).strip()
    tx_match = _TX_RE.search(stdout)
    tx = tx_match.group(0) if tx_match else ""
    result_json = json.dumps({"verdict": label, "reasoning": reason,
                              "method": "genlayer_consensus"})
    return result_json, tx


# --- genlayer-py path (used by the live services; runs on a server, no CLI) ---
_VERDICT_SEG = re.compile(r"VERDICT=([^'\"]+)")
_glp_client = None
_glp_account = None


def _glp():
    """Lazy studionet client + account (a fresh key works; gas is sponsored)."""
    global _glp_client, _glp_account
    if _glp_client is None:
        from genlayer_py import (create_client, create_account,
                                 generate_private_key, studionet)
        pk = os.environ.get("GENLAYER_PRIVATE_KEY") or generate_private_key()
        _glp_account = create_account(pk)
        _glp_client = create_client(chain=studionet, account=_glp_account)
    return _glp_client, _glp_account


def call_contract(addr: str, method: str, args: list, timeout: int = 300):
    """Call a VeriClaw GenLayer contract method via genlayer-py and parse the
    consensus verdict. Returns (label, reason, extras, tx_hash). `extras` are the
    trailing ' ~~ ' fields some contracts append (Trust Oracle: resolved_ca,
    resolved_chain, namesakes)."""
    client, account = _glp()
    tx = client.write_contract(address=addr, function_name=method,
                               args=list(args), account=account)
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx, retries=max(10, timeout // 3), interval=3000)
    text = str(receipt)
    m = _VERDICT_SEG.search(text)
    if not m:
        raise RuntimeError("could not parse verdict from receipt")
    label_part, _, rest = m.group(1).partition("|")
    parts = rest.split(" ~~ ")
    label = label_part.strip().lower()
    reason = parts[0].strip()
    extras = [p.strip() for p in parts[1:]]
    tx_hash = tx if isinstance(tx, str) else getattr(tx, "hex", lambda: str(tx))()
    return label, reason, extras, tx_hash


def make_genlayer_call(timeout: int = 300):
    addr = os.environ["GENLAYER_VERIFIER_ADDRESS"]

    def call(kind: str, content: str, sources: str):
        last_err = None
        for _ in range(2):  # one retry: studionet consensus is occasionally flaky
            proc = subprocess.run(
                ["genlayer", "write", addr, "verify", "--args", kind, content, sources],
                capture_output=True, text=True, timeout=timeout,
            )
            try:
                return _parse_cli_output(proc.stdout + proc.stderr)
            except RuntimeError as e:
                last_err = e
        raise last_err

    return call
