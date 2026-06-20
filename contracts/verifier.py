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
    def verify(self, kind: str, payload: str) -> str:
        if kind not in VALID:
            raise gl.vm.UserError("unknown kind: " + str(kind))
        allowed = VALID[kind]

        def gen() -> str:
            if kind == "claim":
                instr = ("Decide whether the statement is supported by the evidence. "
                         "The label must be one of: supported, refuted, inconclusive.")
            else:
                instr = ("Decide whether the deliverable meets the acceptance criteria. "
                         "The label must be one of: pass, fail, inconclusive.")
            prompt = ("You are a strict, impartial verifier. " + instr + "\n"
                      "Reply on ONE line exactly as: VERDICT=<label>|<one short sentence of reasoning>\n"
                      "Input: " + payload)
            out = gl.nondet.exec_prompt(prompt)
            return _normalize(str(out), allowed)

        res = gl.eq_principle.prompt_comparative(
            gen,
            "Equivalent if the VERDICT label (before the |) matches exactly; "
            "the reasoning wording after the | may differ.",
        )
        raw = res.get() if hasattr(res, "get") else res
        label, reason = _split_verdict(str(raw), allowed)
        return json.dumps({"verdict": label, "reasoning": reason,
                           "method": "genlayer_consensus"})


def _normalize(text: str, allowed) -> str:
    """Coerce an LLM reply into the canonical 'VERDICT=<label>|<reason>' line."""
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
