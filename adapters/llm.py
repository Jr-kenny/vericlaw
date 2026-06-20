"""Claude-backed LLM callable for the verifier.

Returns a `callable(prompt: str) -> str` that the LocalLLMVerifier uses. The
model is configurable via CLAUDE_MODEL (defaults to a current Sonnet, a good
balance of judgement and cost for a high-volume verifier).
"""
import os


def make_claude_llm():
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    def call(prompt: str) -> str:
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in msg.content
                       if getattr(block, "type", None) == "text")

    return call
