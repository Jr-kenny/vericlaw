import json
from adapters.genlayer_call import _parse_cli_output, _flatten

SAMPLE = """- Calling write method verify on contract at 0xFF06...
Write Transaction Hash:
0x1bc172fa6dd30948135f94cb166a062e2f30c84ea4116b8ca585f16887bf1d42
  consensus_data: {
              readable: '"VERDICT=supported|The chemical symbol for gold is Au, derived from the Latin word aurum."'
  }
"""


def test_parse_extracts_verdict_reasoning_and_tx():
    result_json, tx = _parse_cli_output(SAMPLE)
    data = json.loads(result_json)
    assert data["verdict"] == "supported"
    assert "aurum" in data["reasoning"]
    assert data["method"] == "genlayer_consensus"
    assert tx == "0x1bc172fa6dd30948135f94cb166a062e2f30c84ea4116b8ca585f16887bf1d42"


def test_parse_raises_when_no_verdict():
    try:
        _parse_cli_output("no verdict here")
        assert False, "should have raised"
    except RuntimeError:
        pass


def test_flatten_turns_json_into_plain_text():
    text = _flatten('{"statement": "the sky is blue", "evidence": ["a", "b"]}')
    assert not text.startswith("{")
    assert "statement: the sky is blue" in text
    assert "evidence:" in text
