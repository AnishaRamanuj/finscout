"""Claude Opus 5.5 (reasoning) + Haiku 5.5 (fast)."""
from anthropic import Anthropic

from app.config import settings
from app.llm.base import LLMProvider, CompletionRequest


class AnthropicProvider(LLMProvider):
    def __init__(self):
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.reasoning_model = settings.model_reasoning
        self.fast_model = settings.model_fast

    def _call(self, model: str, req: CompletionRequest) -> str:
        kwargs = dict(
            model=model,
            max_tokens=req.max_tokens,
            system=req.system,
            messages=[{"role": "user", "content": req.user}],
        )
        if req.extended_thinking:
            kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": min(10000, req.max_tokens * 3),
            }

        resp = self.client.messages.create(**kwargs)
        blocks = [b.text for b in resp.content if hasattr(b, "text")]
        return "\n".join(blocks).strip()

    def reasoning(self, req: CompletionRequest) -> str:
        return self._call(self.reasoning_model, req)

    def fast(self, req: CompletionRequest) -> str:
        req.extended_thinking = False
        return self._call(self.fast_model, req)
