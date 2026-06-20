# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json

# chain name -> GoPlus EVM chain id
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
            evidence = []
            if chain in ("solana", "sol"):
                gp = ("https://api.gopluslabs.io/api/v1/solana/token_security"
                      "?contract_addresses=" + target)
            else:
                cid = GOPLUS_CHAIN.get(chain, "1")
                gp = ("https://api.gopluslabs.io/api/v1/token_security/" + cid
                      + "?contract_addresses=" + target)
            try:
                r = gl.nondet.web.get(gp)
                evidence.append("GOPLUS_SECURITY: " + r.body.decode("utf-8")[:2000])
            except Exception:
                pass
            try:
                r2 = gl.nondet.web.get(
                    "https://api.dexscreener.com/latest/dex/tokens/" + target)
                evidence.append("DEXSCREENER_LIQUIDITY: "
                                + r2.body.decode("utf-8")[:1500])
            except Exception:
                pass
            if len(evidence) > 0:
                bundle = "\n".join(evidence)
            else:
                bundle = "(no security or liquidity data could be retrieved)"

            prompt = (
                "You are a strict onchain risk analyst. Using ONLY the security and "
                "liquidity data below, assess how safe this token/contract is. Weigh: "
                "honeypot / cannot-sell flags, owner powers (mint, blacklist, "
                "modifiable tax/fees), proxy/upgradeable risk, whether liquidity is "
                "real and locked, and holder concentration. If almost no data was "
                "retrieved, lean toward caution, not safe.\n"
                "Pick ONE label: safe (no material red flags), caution (minor or "
                "unclear risks), high_risk (serious red flags), scam (honeypot or "
                "clear rug indicators).\n"
                "Reply on ONE line exactly as: VERDICT=<label>|<one or two sentences "
                "naming the key red and green flags>\n"
                "TARGET: " + target + "  CHAIN: " + chain + "\n\nDATA:\n" + bundle + "\n"
            )
            return _normalize(str(gl.nondet.exec_prompt(prompt)))

        res = gl.eq_principle.prompt_comparative(
            gen,
            "Equivalent if the VERDICT risk label (before the |) matches exactly; "
            "the specific flags named after the | may differ in wording.",
        )
        raw = res.get() if hasattr(res, "get") else res
        label, reason = _split(str(raw))
        return json.dumps({"verdict": label, "reasoning": reason,
                           "method": "genlayer_consensus",
                           "target": target, "chain": chain})


def _normalize(text: str) -> str:
    label, reason = _split(text)
    return "VERDICT=" + label + "|" + reason


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
