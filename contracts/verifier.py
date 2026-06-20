# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json

VALID = {
    "claim": ("supported", "refuted", "inconclusive"),
    "deliverable": ("pass", "fail", "inconclusive"),
}


class VeriClawVerifier(gl.Contract):
    owner: Address

    def __init__(self):
        self.owner = gl.message.sender_address

    @gl.public.write
    def verify(self, kind: str, content: str, sources: str) -> str:
        if kind not in VALID:
            raise gl.vm.UserError("unknown kind: " + str(kind))
        allowed = VALID[kind]
        content = str(content)
        sources = str(sources)
        src_urls = [u.strip() for u in sources.split("\n") if u.strip().startswith("http")]

        def gen() -> str:
            evidence = []
            for u in src_urls[:3]:
                try:
                    r = gl.nondet.web.get(u)
                    if int(getattr(r, "status", 200) or 200) == 200:
                        evidence.append("SOURCE " + u + ": "
                                        + r.body.decode("utf-8")[:1200])
                except Exception:
                    pass
            if len(evidence) > 0:
                bundle = "\n".join(evidence)
            else:
                bundle = "(no external sources provided)"

            if kind == "claim":
                instr = ("Decide whether the CLAIM is true. The label must be one of: "
                         "supported, refuted, inconclusive.")
            else:
                instr = ("Decide whether the DELIVERABLE meets its acceptance criteria. "
                         "The label must be one of: pass, fail, inconclusive.")
            prompt = (
                "You are a strict, impartial verifier. " + instr + "\n"
                "Prefer the EVIDENCE when it is present. If no evidence was retrieved, "
                "judge from well-established knowledge, and use the inconclusive label "
                "only when you genuinely cannot decide.\n"
                "Reply on ONE line exactly as: VERDICT=<label>|<one short sentence of reasoning>\n"
                "INPUT: " + content + "\n\nEVIDENCE:\n" + bundle + "\n"
            )
            return _normalize(str(gl.nondet.exec_prompt(prompt)), allowed)

        res = gl.eq_principle.prompt_comparative(
            gen,
            "Equivalent if the VERDICT label (before the |) matches exactly; "
            "the reasoning wording after the | may differ.",
        )
        raw = res.get() if hasattr(res, "get") else res
        label, reason = _split_verdict(str(raw), allowed)
        return json.dumps({"verdict": label, "reasoning": reason,
                           "method": "genlayer_consensus",
                           "sources_used": len(src_urls)})


def _normalize(text: str, allowed) -> str:
    label, reason = _split_verdict(text, allowed)
    return "VERDICT=" + label + "|" + reason


def _split_verdict(text: str, allowed):
    body = text.split("VERDICT=", 1)[-1].strip()
    label_part, _, reason = body.partition("|")
    label = label_part.strip().lower()
    if label not in allowed:
        low = text.lower()
        label = "inconclusive"
        for cand in allowed:
            if cand in low:
                label = cand
                break
    return label, reason.strip()
