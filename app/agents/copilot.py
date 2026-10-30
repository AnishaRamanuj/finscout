"""Portfolio Copilot — Claude Opus 5.5 answers questions about your holdings."""
from anthropic import Anthropic
from app.config import settings

_client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None

SYSTEM_PROMPT = """You are a personal equity research analyst for an individual investor's own portfolio.

Rules:
- Answer with specific evidence from the data provided.
- Always cite exact numbers (price, score, growth, etc.).
- Compare holdings against each other where relevant.
- NEVER give direct buy/sell advice. Explain the signals and let the user decide.
- Keep answers under 200 words.
"""


def answer_portfolio_question(portfolio_context: str, question: str) -> str:
    if not _client:
        return "Set ANTHROPIC_API_KEY in .env to use the Copilot."

    resp = _client.messages.create(
        model=settings.model_reasoning,
        max_tokens=1200,
        thinking={"type": "enabled", "budget_tokens": 4000},
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"PORTFOLIO:\n{portfolio_context}\n\nQUESTION: {question}",
        }],
    )
    text_blocks = [b.text for b in resp.content if hasattr(b, "text")]
    return "\n".join(text_blocks).strip()
