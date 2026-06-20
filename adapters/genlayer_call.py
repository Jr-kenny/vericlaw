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
