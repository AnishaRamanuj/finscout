"""Portfolio Copilot — answers questions about the user's holdings."""
from app.llm import get_llm
from app.llm.base import CompletionRequest


SYSTEM = """You are a personal equity research analyst for an individual investor's portfolio.

Rules:
- Answer with specific evidence from the data provided.
- Always cite exact numbers (price, score, growth, etc.).
- Compare holdings against each other where relevant.
- NEVER give direct buy/sell advice. Explain the signals and let the user decide.
- Keep answers under 200 words.
"""


def answer_portfolio_question(portfolio_context: str, question: str) -> str:
    user = f"PORTFOLIO:\n{portfolio_context}\n\nQUESTION: {question}"
    try:
        return get_llm().reasoning(CompletionRequest(
            system=SYSTEM,
            user=user,
            max_tokens=1200,
            extended_thinking=True,
        ))
    except Exception as e:
        return f"(LLM unavailable: {e})"
