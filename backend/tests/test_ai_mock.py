from app.services.ai_service import MockAIService


def test_mock_ai_deterministic_suggestions():
    svc = MockAIService()
    context = {'project_id': 1, 'changed_field': 'context', 'content': 'ml security in finance'}
    a = svc.suggest_fields(context)
    b = svc.suggest_fields(context)
    assert a.payload == b.payload
