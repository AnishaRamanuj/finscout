"""Returns the LLM provider selected in .env — one switch for the whole app."""
from functools import lru_cache

from app.config import settings
from app.llm.base import LLMProvider


@lru_cache(maxsize=1)
def get_llm() -> LLMProvider:
    provider = settings.llm_provider.lower().strip()

    if provider == "anthropic":
        from app.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider()

    if provider == "ollama":
        from app.llm.ollama_provider import OllamaProvider
        return OllamaProvider()

    raise ValueError(
        f"Unknown LLM_PROVIDER='{provider}'. Supported: anthropic | ollama."
    )
