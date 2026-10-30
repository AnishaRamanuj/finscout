"""Claude Opus 5.5 writes a one-paragraph 'Why Now' for each pick."""
from anthropic import Anthropic
from app.config import settings

_client = Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None


def generate_why_now(ticker: str, name: str, scores: dict, data: dict) -> str:
    if not _client:
        return "Set ANTHROPIC_API_KEY in .env to generate explanations."

    prompt = f"""Write exactly ONE paragraph (max 65 words) titled "Why Now" for {name} ({ticker}).

Score breakdown (0-100): {scores}

Latest data:
- Sector: {data.get('sector')}
- Market cap: {data.get('market_cap')}
- PE: {data.get('pe')}
- Price: {data.get('price')}
- ROCE: {data.get('roce')}

Rules:
- Use plain English a retail investor understands.
- Cite exact numbers from the data above.
- End with ONE short risk sentence prefixed with "Risk:".
- No disclaimers, no "consult a financial advisor".
"""
    resp = _client.messages.create(
        model=settings.model_reasoning,
        max_tokens=400,
        thinking={"type": "enabled", "budget_tokens": 2000},
        messages=[{"role": "user", "content": prompt}],
    )
    text_blocks = [b.text for b in resp.content if hasattr(b, "text")]
    return "\n".join(text_blocks).strip()
