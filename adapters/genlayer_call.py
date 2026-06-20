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


def call_contract(addr: str, method: str, args: list, timeout: int = 300):
    """Call any VeriClaw GenLayer contract method and parse its consensus output.

    Returns (label, reason, extras, tx_hash). `extras` are the trailing ' ~~ '
    fields some contracts append after the reason (e.g. the Trust Oracle's
    resolved_ca/chain/namesakes). Raises on a transient miss after one retry.
    """
    last_err = None
    for _ in range(2):
        proc = subprocess.run(
            ["genlayer", "write", addr, method, "--args", *args],
            capture_output=True, text=True, timeout=timeout,
        )
        out = proc.stdout + proc.stderr
        m = _VERDICT_RE.search(out)
        if m:
            label = m.group(1).strip().lower()
            parts = m.group(2).split(" ~~ ")
            reason = parts[0].strip()
            extras = [p.strip() for p in parts[1:]]
            tx_match = _TX_RE.search(out)
            return label, reason, extras, (tx_match.group(0) if tx_match else "")
        last_err = RuntimeError("could not parse verdict from CLI output")
    raise last_err


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
