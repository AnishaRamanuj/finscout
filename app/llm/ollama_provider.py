"""Ollama — run everything locally for free. No API key, no internet needed."""
import httpx

from app.config import settings
from app.llm.base import LLMProvider, CompletionRequest


class OllamaProvider(LLMProvider):
    """
    Uses Ollama's HTTP API at http://localhost:11434.

    One-time setup:
      1. Install: https://ollama.com/download
      2. Pull models:
             ollama pull qwen2.5:14b     # reasoning (needs ~10GB RAM)
             ollama pull llama3.2:3b     # fast (needs ~3GB RAM)
      3. Keep Ollama running in the background.

    If you have less RAM, use smaller models:
      - qwen2.5:7b (needs ~5GB)
      - llama3.2:1b (needs ~2GB)
    """

    def __init__(self):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.reasoning_model = settings.ollama_reasoning_model
        self.fast_model = settings.ollama_fast_model
        self.timeout = 300  # local inference can be slow on CPU

    def _call(self, model: str, req: CompletionRequest) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": req.system},
                {"role": "user", "content": req.user},
            ],
            "stream": False,
            "options": {
                "num_predict": req.max_tokens,
                "temperature": req.temperature,
            },
        }
        r = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()

    def reasoning(self, req: CompletionRequest) -> str:
        return self._call(self.reasoning_model, req)

    def fast(self, req: CompletionRequest) -> str:
        return self._call(self.fast_model, req)
