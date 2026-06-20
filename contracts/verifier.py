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
            raise Exception("unknown kind: " + str(kind))
        allowed = VALID[kind]

        def _decide():
            return self._decide_nondet(kind, payload, allowed)

        label = gl.eq_principle.strict_eq(_decide)
        return json.dumps({"verdict": label, "method": "genlayer_consensus"})

    def _decide_nondet(self, kind: str, payload: str, allowed) -> str:
        if kind == "claim":
            task = ("Decide whether the statement is supported by the evidence. "
                    "Reply with exactly one word: supported, refuted, or inconclusive.")
        else:
            task = ("Decide whether the deliverable meets the acceptance criteria. "
                    "Reply with exactly one word: pass, fail, or inconclusive.")
        sys_prompt = "You are a strict, impartial verifier. " + task
        user_prompt = "Input: " + payload
        res = gl.nondet.exec_prompt(
            providers=["openai", "anthropic", "google"],
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        text = res.choices[0].message.content.strip().lower()
        for label in allowed:
            if label in text:
                return label
        return "inconclusive"
