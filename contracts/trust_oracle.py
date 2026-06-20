# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json

# chain name / DEXScreener chainId -> GoPlus EVM chain id
GOPLUS_CHAIN = {
    "ethereum": "1", "eth": "1", "bsc": "56", "bnb": "56", "base": "8453",
    "arbitrum": "42161", "arb": "42161", "polygon": "137", "matic": "137",
    "optimism": "10", "op": "10", "avalanche": "43114", "avax": "43114",
}
LABELS = ("safe", "caution", "high_risk", "scam")


class TrustOracle(gl.Contract):
    owner: Address

    def __init__(self):
        self.owner = gl.message.sender_address

    @gl.public.write
    def trust_check(self, target: str, chain: str) -> str:
        target = str(target).strip()
        chain = str(chain).strip().lower()

        def gen() -> str:
            is_evm_ca = target.startswith("0x") and len(target) == 42
            is_sol_ca = (chain in ("solana", "sol") and not is_evm_ca
                         and 32 <= len(target) <= 44 and target.isalnum())

            ca = ""
            resolved_chain = chain
            namesakes = 0
            search_summary = ""

            if is_evm_ca or is_sol_ca:
                ca = target
            else:
                # resolve a ticker / name / url to the canonical (most-liquid) token
                try:
                    sr = gl.nondet.web.get(
                        "https://api.dexscreener.com/latest/dex/search?q=" + target)
                    pairs = json.loads(sr.body.decode("utf-8")).get("pairs", []) or []
                    best_liq = -1.0
                    seen = []
                    for p in pairs:
                        pcid = str(p.get("chainId", "")).lower()
                        if chain != "" and chain not in ("any", pcid):
                            continue
                        addr = str(p.get("baseToken", {}).get("address", ""))
                        if addr != "" and addr not in seen:
                            seen.append(addr)
                        usd = float(p.get("liquidity", {}).get("usd", 0) or 0)
                        if usd > best_liq:
                            best_liq = usd
                            ca = addr
                            resolved_chain = pcid
                    namesakes = len(seen)
                    search_summary = ("resolved '" + target + "' -> " + ca
                                      + " on " + resolved_chain + "; "
                                      + str(namesakes) + " distinct token(s) share this name/query")
                except Exception:
                    pass

            evidence = []
            if search_summary != "":
                evidence.append("RESOLUTION: " + search_summary)
            if ca == "":
                evidence.append("RESOLUTION: could not resolve the target to a token")

            if ca != "":
                if resolved_chain in ("solana", "sol"):
                    gp = ("https://api.gopluslabs.io/api/v1/solana/token_security"
                          "?contract_addresses=" + ca)
                else:
                    cid = GOPLUS_CHAIN.get(resolved_chain, "1")
                    gp = ("https://api.gopluslabs.io/api/v1/token_security/" + cid
                          + "?contract_addresses=" + ca)
                try:
                    r = gl.nondet.web.get(gp)
                    # keep the full record: holders[], lp_holders[] (lock status),
                    # owner/creator balances all live here and must not be truncated
                    evidence.append("GOPLUS_SECURITY: " + r.body.decode("utf-8")[:5000])
                except Exception:
                    pass
                try:
                    r2 = gl.nondet.web.get(
                        "https://api.dexscreener.com/latest/dex/tokens/" + ca)
                    # pairs carry pairCreatedAt (age), liquidity.usd, volume, fdv
                    evidence.append("DEXSCREENER_LIQUIDITY: "
                                    + r2.body.decode("utf-8")[:3000])
                except Exception:
                    pass

            if len(evidence) > 0:
                bundle = "\n".join(evidence)
            else:
                bundle = "(no data could be retrieved)"

            prompt = (
                "You are a strict onchain risk analyst. Using ONLY the data below, "
                "assess how safe this token is. Weigh ALL of: honeypot / cannot-sell "
                "flags; buy/sell tax; owner powers (mint, blacklist, can-take-back-"
                "ownership, modifiable tax); proxy/upgradeable; HOLDER CONCENTRATION "
                "(top holders' percent, owner_balance and creator_balance percent, "
                "holder_count); LIQUIDITY depth and LP LOCK (lp_holders is_locked and "
                "percent and the locker tag, how much is locked); and TOKEN/PAIR AGE "
                "(pairCreatedAt: a very recently created pair is higher risk). If the "
                "target resolved to a token but MANY tokens share the name, warn about "
                "impersonation. If little or no data was retrieved, lean to caution, "
                "not safe.\n"
                "Pick ONE label: safe, caution, high_risk, scam.\n"
                "Reply on ONE line exactly as: VERDICT=<label>|<one or two sentences: "
                "which token (address/chain) you judged, and the key red/green flags>\n"
                "TARGET: " + target + "  CHAIN: " + chain + "\n\nDATA:\n" + bundle + "\n"
            )
            v_label, v_reason = _split(str(gl.nondet.exec_prompt(prompt)))
            return ("VERDICT=" + v_label + "|" + v_reason + " ~~ " + ca
                    + " ~~ " + resolved_chain + " ~~ " + str(namesakes))

        res = gl.eq_principle.prompt_comparative(
            gen,
            "Equivalent if the VERDICT risk label (before the |) matches exactly; "
            "the reasoning wording and the resolved-token metadata after may differ.",
        )
        raw = res.get() if hasattr(res, "get") else res
        label, reason, rca, rchain, ns = _parse_full(str(raw), chain)
        return json.dumps({"verdict": label, "reasoning": reason,
                           "resolved_ca": rca, "resolved_chain": rchain,
                           "namesakes": ns, "method": "genlayer_consensus",
                           "target": target, "chain": chain})


def _parse_full(text: str, default_chain: str):
    parts = text.split(" ~~ ")
    label, reason = _split(parts[0])
    rca = parts[1].strip() if len(parts) > 1 else ""
    rchain = parts[2].strip() if len(parts) > 2 else default_chain
    ns = 0
    if len(parts) > 3:
        try:
            ns = int(parts[3].strip())
        except Exception:
            ns = 0
    return label, reason, rca, rchain, ns


def _split(text: str):
    body = text.split("VERDICT=", 1)[-1].strip()
    label_part, _, reason = body.partition("|")
    label = label_part.strip().lower().replace(" ", "_")
    if label not in LABELS:
        low = text.lower()
        label = "caution"
        for cand in LABELS:
            if cand in low:
                label = cand
                break
    return label, reason.strip()
