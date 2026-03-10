import hashlib

from app.core.config import settings


class LLMClient:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    def generate(self, prompt: str) -> str:
        digest = hashlib.sha256(prompt.encode('utf-8')).hexdigest()[:12]
        return f'Mock suggestion ({digest}): refine this canvas item using the existing run context.'


class OpenAILLMClient(LLMClient):
    def generate(self, prompt: str) -> str:
        # Provider-agnostic stub for the artifact. Falls back to deterministic mode.
        digest = hashlib.sha256((settings.llm_model + prompt).encode('utf-8')).hexdigest()[:12]
        return f'LLM fallback suggestion ({digest}): refine this canvas item using the existing run context.'


def get_llm_client() -> LLMClient:
    if settings.ai_mode == 'on' and settings.llm_api_key:
        return OpenAILLMClient()
    return MockLLMClient()
