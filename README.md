# verify.croo

A paid agent on the CROO Agent Protocol (CAP). Other agents call it to verify
something and get back a signed verdict:

- `claim` - is this statement true, checked against live web evidence
- `deliverable` - does this output meet the agreed acceptance criteria
- `onchain` - attest an on-chain fact (a tx happened, a balance, a contract)

Subjective verdicts are decided by a GenLayer intelligent contract running
multi-validator LLM consensus, with the GenLayer transaction returned as proof.

Setup, the SDK methods used, and the integration guide are filled in as the
build progresses. See `docs/superpowers/` for the design and plan.
