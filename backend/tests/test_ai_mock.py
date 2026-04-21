from app.services.llm_client import MockLLMClient, OpenAILLMClient, get_llm_client
from app.services.ai_service import AISuggestionService


def test_mock_llm_is_deterministic():
    client = MockLLMClient()
    prompt = 'Generate suggestions for run context: security and ml'
    assert client.generate(prompt) == client.generate(prompt)


def test_openai_client_is_selected_when_api_key_is_present(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', 'test-key')
    client = get_llm_client()
    assert isinstance(client, OpenAILLMClient)


def test_mock_client_is_selected_when_api_key_is_missing(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    client = get_llm_client()
    assert isinstance(client, MockLLMClient)


def test_openai_client_uses_responses_api(monkeypatch):
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)

            class FakeResponse:
                output_text = 'Generated recommendation'

            return FakeResponse()

    class FakeOpenAI:
        def __init__(self, api_key, timeout):
            captured['api_key'] = api_key
            captured['timeout'] = timeout
            self.responses = FakeResponses()

    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', 'test-key')
    monkeypatch.setattr('app.services.llm_client.settings.llm_model', 'gpt-test')
    monkeypatch.setattr('app.services.llm_client.settings.llm_timeout_seconds', 12)
    monkeypatch.setitem(__import__('sys').modules, 'openai', type('FakeModule', (), {'OpenAI': FakeOpenAI}))

    client = OpenAILLMClient()
    text = client.generate('Recommend something concise')

    assert text == 'Generated recommendation'
    assert captured['api_key'] == 'test-key'
    assert captured['timeout'] == 12
    assert captured['model'] == 'gpt-test'
    assert captured['input'] == 'Recommend something concise'


def test_method_prompt_requires_academic_references():
    service = AISuggestionService.__new__(AISuggestionService)

    class Question:
        key = 'method'
        title = 'What scientific evidence?'
        prompt_template = 'Present the initial scoping of scientific evidence.'

    prompt = service._prompt_for_question(
        Question(),
        'Describe the pain point: Teams struggle to integrate data scientists into delivery squads.',
    )

    assert 'Include 1 to 3 academic references' in prompt
    assert 'Kim et al.' in prompt


def test_identify_people_prompt_limits_groups_and_disallows_lead_in():
    service = AISuggestionService.__new__(AISuggestionService)

    class Question:
        key = 'hypotheses'
        title = 'Identify People Involved'
        prompt_template = 'Identify the people directly and indirectly involved.'

    prompt = service._prompt_for_question(
        Question(),
        'Describe the pain point: Teams struggle to maintain ML code with weak software design practices.',
    )

    assert 'Return 3 to 5 groups of people involved' in prompt
    assert 'never more than 5' in prompt
    assert 'Start directly with the groups' in prompt
    assert 'Do not begin with introductory framing' in prompt
