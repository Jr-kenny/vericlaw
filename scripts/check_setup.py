"""One-time setup check.

- Generates a dedicated attestation signing key into .env if missing (prints only
  the public address, never the private key).
- Confirms the CROO SDK key authenticates by making one read call.

Run: python scripts/check_setup.py
"""
import asyncio
import os
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_env() -> dict:
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


def set_env_value(key: str, value: str) -> None:
    lines = ENV_PATH.read_text().splitlines()
    out, found = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def ensure_signing_key(env: dict) -> None:
    if env.get("WALLET_PRIVATE_KEY"):
        from eth_account import Account
        addr = Account.from_key(env["WALLET_PRIVATE_KEY"]).address
        print(f"[signing key] already set, address {addr}")
        return
    from eth_account import Account
    acct = Account.create()
    set_env_value("WALLET_PRIVATE_KEY", acct.key.hex())
    print(f"[signing key] generated, address {acct.address}")


async def check_croo(env: dict) -> None:
    from croo import AgentClient, Config, ListOptions
    if not env.get("CROO_SDK_KEY") or env["CROO_SDK_KEY"].endswith("..."):
        print("[croo] no SDK key set, skipping auth check")
        return
    client = AgentClient(Config(base_url=env["CROO_API_URL"],
                                ws_url=env.get("CROO_WS_URL", "")),
                         env["CROO_SDK_KEY"])
    try:
        negs = await client.list_negotiations(ListOptions(page_size=1, role="provider"))
        print(f"[croo] SDK key OK. authenticated read returned {len(negs)} negotiation(s)")
    except Exception as e:
        print(f"[croo] auth check failed: {type(e).__name__}: {e}")
    finally:
        await client.close()


def main():
    env = load_env()
    ensure_signing_key(env)
    asyncio.run(check_croo(load_env()))


if __name__ == "__main__":
    main()
