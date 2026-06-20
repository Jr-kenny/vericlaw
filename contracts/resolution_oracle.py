# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json

LABELS = ("yes", "no", "undetermined")


class ResolutionOracle(gl.Contract):
    owner: Address

    def __init__(self):
        self.owner = gl.message.sender_address

    @gl.public.write
    def resolve(self, event: str, sources: str) -> str:
        event = str(event)
        sources = str(sources)
        src_urls = [u.strip() for u in sources.split("\n") if u.strip().startswith("http")]

        def gen() -> str:
            evidence = []
            for u in src_urls[:4]:
                try:
                    r = gl.nondet.web.get(u)
                    if int(getattr(r, "status", 200) or 200) == 200:
                        evidence.append("SOURCE " + u + ": "
                                        + r.body.decode("utf-8")[:1500])
                except Exception:
                    pass
            if len(evidence) > 0:
                bundle = "\n".join(evidence)
            else:
                bundle = "(no sources provided; judge from well-established fact)"

            prompt = (
                "You are a strict, impartial outcome resolver for prediction markets. "
                "Decide whether the EVENT has actually happened or is true, using the "
                "EVIDENCE. Use 'yes' only if clearly confirmed, 'no' if clearly false "
                "or it did not happen, and 'undetermined' if it is in the future, not "
                "yet decided, ambiguous, or the evidence is insufficient. Never guess.\n"
                "Reply on ONE line exactly as: VERDICT=<yes|no|undetermined>|<one short "
                "sentence citing the deciding evidence>\n"
                "EVENT: " + event + "\n\nEVIDENCE:\n" + bundle + "\n"
            )
            return _normalize(str(gl.nondet.exec_prompt(prompt)))

        res = gl.eq_principle.prompt_comparative(
            gen,
            "Equivalent if the VERDICT outcome label (before the |) matches exactly; "
            "the reasoning wording after may differ.",
        )
        raw = res.get() if hasattr(res, "get") else res
        label, reason = _split(str(raw))
        return json.dumps({"outcome": label, "reasoning": reason,
                           "method": "genlayer_consensus", "event": event})


def _normalize(text: str) -> str:
    label, reason = _split(text)
    return "VERDICT=" + label + "|" + reason


def _split(text: str):
    body = text.split("VERDICT=", 1)[-1].strip()
    label_part, _, reason = body.partition("|")
    label = label_part.strip().lower()
    if label not in LABELS:
        low = text.lower()
        label = "undetermined"
        for cand in LABELS:
            if cand in low:
                label = cand
                break
    return label, reason.strip()
