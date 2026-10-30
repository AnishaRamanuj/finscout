"""Common interface every LLM provider implements."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class CompletionRequest:
    system: str
    user: str
    max_tokens: int = 1000
    temperature: float = 0.3
    extended_thinking: bool = False  # only Claude uses this


class LLMProvider(ABC):
    """Abstract base. Two tiers: 'reasoning' (smart) and 'fast' (cheap/local)."""

    @abstractmethod
    def reasoning(self, req: CompletionRequest) -> str:
        """Deep reasoning — Claude Opus 5.5 or an equivalent local model."""

    @abstractmethod
    def fast(self, req: CompletionRequest) -> str:
        """High-volume, cheap — Claude Haiku 5.5 or a small local model."""
