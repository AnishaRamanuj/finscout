"""Writes a one-paragraph 'Why Now' for each pick — uses whichever LLM is configured."""
from app.llm import get_llm
from app.llm.base import CompletionRequest


SYSTEM = (
    "You are a senior equity research analyst writing a one-paragraph summary "
    "for a retail investor. Use plain English. Cite exact numbers. "
    "End with ONE short risk sentence prefixed with 'Risk:'. "
    "No disclaimers, no 'consult a financial advisor'."
)


def generate_why_now(ticker: str, name: str, scores: dict, data: dict) -> str:
    user = f"""Write exactly ONE paragraph (max 65 words) titled "Why Now" for {name} ({ticker}).

Score breakdown (0-100): {scores}

Latest data:
- Sector: {data.get('sector')}
- Market cap: {data.get('market_cap')}
- PE: {data.get('pe')}
- Price: {data.get('price')}
- ROCE: {data.get('roce')}
"""
    try:
        return get_llm().reasoning(CompletionRequest(
            system=SYSTEM,
            user=user,
            max_tokens=400,
            extended_thinking=True,
        ))
    except Exception as e:
        return f"(LLM unavailable: {e})"
