# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json

LABELS = ("pass", "partial", "fail")


class DeliverableAuditor(gl.Contract):
    owner: Address

    def __init__(self):
        self.owner = gl.message.sender_address

    @gl.public.write
    def audit(self, criteria: str, deliverable: str, sources: str) -> str:
        criteria = str(criteria)
        deliverable = str(deliverable)
        sources = str(sources)
        src_urls = [u.strip() for u in sources.split("\n") if u.strip().startswith("http")]

        def gen() -> str:
            evidence = []
            for u in src_urls[:4]:
                try:
                    r = gl.nondet.web.get(u)
                    if int(getattr(r, "status", 200) or 200) == 200:
                        evidence.append("CITED_SOURCE " + u + ": "
                                        + r.body.decode("utf-8")[:1500])
                except Exception:
                    pass
            if len(evidence) > 0:
                cited = "\n".join(evidence)
            else:
                cited = "(no sources cited)"

            prompt = (
                "You are a strict, impartial reviewer auditing whether a DELIVERABLE "
                "meets its ACCEPTANCE CRITERIA. Check each criterion against the "
                "deliverable. If the deliverable makes factual claims and cited sources "
                "were fetched below, verify those claims are actually supported by the "
                "sources and flag any unsupported or fabricated ones.\n"
                "Label: pass (all criteria clearly met), partial (some met, some not), "
                "fail (key criteria unmet, or claims contradicted/unsupported).\n"
                "Reply on ONE line exactly as: VERDICT=<pass|partial|fail>|<one or two "
                "sentences naming which criteria passed and which failed>\n"
                "ACCEPTANCE CRITERIA: " + criteria + "\n\n"
                "DELIVERABLE: " + deliverable + "\n\n"
                "CITED_SOURCE CONTENT:\n" + cited + "\n"
            )
            return _normalize(str(gl.nondet.exec_prompt(prompt)))

        res = gl.eq_principle.prompt_comparative(
            gen,
            "Equivalent if the VERDICT label (before the |) matches exactly; the "
            "reasoning wording after may differ.",
        )
        raw = res.get() if hasattr(res, "get") else res
        label, reason = _split(str(raw))
        return json.dumps({"verdict": label, "reasoning": reason,
                           "method": "genlayer_consensus"})


def _normalize(text: str) -> str:
    label, reason = _split(text)
    return "VERDICT=" + label + "|" + reason


def _split(text: str):
    body = text.split("VERDICT=", 1)[-1].strip()
    label_part, _, reason = body.partition("|")
    label = label_part.strip().lower()
    if label not in LABELS:
        low = text.lower()
        label = "partial"
        for cand in LABELS:
            if cand in low:
                label = cand
                break
    return label, reason.strip()
