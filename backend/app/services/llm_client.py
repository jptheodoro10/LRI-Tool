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
    def __init__(self):
        from openai import OpenAI

        api_key = settings.llm_api_key.strip()
        self.client = OpenAI(
            api_key=api_key,
            timeout=settings.llm_timeout_seconds,
        )

    def generate(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=settings.llm_model,
            input=prompt,
        )

        text = (getattr(response, 'output_text', '') or '').strip()
        if text:
            return text

        # Fallback for SDK response variants where `output_text` is empty.
        output = getattr(response, 'output', []) or []
        fragments = []
        for item in output:
            for content in getattr(item, 'content', []) or []:
                if getattr(content, 'type', '') == 'output_text':
                    fragments.append(getattr(content, 'text', ''))

        text = '\n'.join(fragment for fragment in fragments if fragment).strip()
        if text:
            return text

        raise RuntimeError('OpenAI response did not contain any text output')


def get_llm_client() -> LLMClient:
    if settings.llm_api_key.strip():
        return OpenAILLMClient()
    return MockLLMClient()
