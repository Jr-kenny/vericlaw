# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json

ERROR_EXPECTED = "[EXPECTED]"
ERROR_LLM = "[LLM_ERROR]"

VALID = {
    "claim": ("supported", "refuted", "inconclusive"),
    "deliverable": ("pass", "fail", "inconclusive"),
}


def _build_prompt(kind: str, payload: str, allowed) -> str:
    labels = ", ".join(allowed)
    if kind == "claim":
        task = "Decide whether the statement is supported by the evidence provided."
    else:
        task = "Decide whether the deliverable meets the acceptance criteria."
    return (
        "You are a strict, impartial verifier. " + task + "\n"
        "Input JSON: " + payload + "\n"
        "Respond ONLY with a JSON object of the form "
        '{"verdict": "<one of: ' + labels + '>", '
        '"confidence": <number 0.0 to 1.0>, '
        '"reasoning": "<one or two sentences>"}.'
    )


def _parse_verdict(analysis, allowed) -> dict:
    if not isinstance(analysis, dict):
        raise gl.vm.UserError(ERROR_LLM + " non-dict response")
    verdict = analysis.get("verdict")
    if isinstance(verdict, str):
        verdict = verdict.strip().lower()
    if verdict not in allowed:
        raise gl.vm.UserError(ERROR_LLM + " bad verdict: " + str(verdict))
    raw_conf = analysis.get("confidence", 0.5)
    try:
        confidence = float(raw_conf)
    except (ValueError, TypeError):
        confidence = 0.5
    reasoning = str(analysis.get("reasoning", ""))
    return {"verdict": verdict, "confidence": confidence, "reasoning": reasoning}


def _handle_leader_error(leaders_res, leader_fn) -> bool:
    leader_msg = leaders_res.message if hasattr(leaders_res, "message") else ""
    try:
        leader_fn()
        return False
    except gl.vm.UserError as e:
        validator_msg = e.message if hasattr(e, "message") else str(e)
        if validator_msg.startswith(ERROR_EXPECTED):
            return validator_msg == leader_msg
        return False
    except Exception:
        return False


class VeriClawVerifier(gl.Contract):
    owner: Address
    count: u256

    def __init__(self):
        self.owner = gl.message.sender_address

    @gl.public.view
    def stats(self) -> dict:
        return {"count": self.count, "owner": self.owner.as_hex}

    @gl.public.write
    def verify(self, kind: str, payload: str) -> str:
        if kind not in VALID:
            raise gl.vm.UserError(ERROR_EXPECTED + " unknown kind: " + str(kind))
        allowed = VALID[kind]

        def leader_fn() -> dict:
            prompt = _build_prompt(kind, payload, allowed)
            analysis = gl.nondet.exec_prompt(prompt, response_format="json")
            return _parse_verdict(analysis, allowed)

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return _handle_leader_error(leaders_res, leader_fn)
            mine = leader_fn()
            leader = leaders_res.calldata
            return mine["verdict"] == leader["verdict"]

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        self.count += u256(1)
        return json.dumps(result)
