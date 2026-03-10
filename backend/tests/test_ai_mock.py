from app.services.llm_client import MockLLMClient


def test_mock_llm_is_deterministic():
    client = MockLLMClient()
    prompt = 'Generate suggestions for run context: security and ml'
    assert client.generate(prompt) == client.generate(prompt)
