from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

from app.core.config import settings


@dataclass
class AIResult:
    payload: dict[str, Any]
    fallback_used: bool = False


class AIService:
    def suggest_fields(self, context: dict[str, Any]) -> AIResult:
        raise NotImplementedError

    def summarize_workshop(self, context: dict[str, Any]) -> AIResult:
        raise NotImplementedError


class MockAIService(AIService):
    keyword_map = {
        'security': ('implications', 'Potential compliance and security impact in production systems.'),
        'ml': ('evidence', 'Existing ML maintenance pain points suggest measurable operational impact.'),
        'finance': ('stakeholders', 'Consider compliance officers, risk analysts, and legal teams.'),
    }

    def suggest_fields(self, context: dict[str, Any]) -> AIResult:
        field = context.get('changed_field', '')
        content = (context.get('content') or '').lower()
        project_id = str(context.get('project_id', '0'))
        stable_score = int(hashlib.sha256((project_id + field + content).encode()).hexdigest()[:2], 16) % 3 + 5

        target_field = 'objective'
        suggested = 'Define a measurable objective with timeline and expected industry impact.'
        rationale = 'General LRI heuristic for strengthening problem framing.'

        for kw, value in self.keyword_map.items():
            if kw in content:
                target_field, suggested = value
                rationale = f'Detected keyword "{kw}" in source field.'
                break

        return AIResult(
            payload={
                'suggestions': [
                    {
                        'target_field': target_field,
                        'source_field': field,
                        'suggested_text': suggested,
                        'confidence': stable_score,
                        'rationale': rationale,
                    }
                ]
            }
        )

    def summarize_workshop(self, context: dict[str, Any]) -> AIResult:
        title = context.get('project_title', 'Untitled Project')
        decision = context.get('decision', 'undecided')
        highlights = context.get('highlights', [])
        summary = [
            f'Project: {title}',
            'Summary of LRI workshop outcomes:',
            '- Problem and context were collaboratively refined.',
            '- Evidence and stakeholder framing were consolidated.',
            f'- Final decision: {decision}.',
        ]
        for item in highlights[:5]:
            summary.append(f'- {item}')
        return AIResult(payload={'summary_text': '\n'.join(summary), 'highlights': highlights[:5]})


class LLMAIService(AIService):
    def __init__(self, mock: MockAIService):
        self.mock = mock

    def suggest_fields(self, context: dict[str, Any]) -> AIResult:
        # Placeholder external call. For artifact reproducibility, failover to mock.
        if not settings.llm_api_key:
            result = self.mock.suggest_fields(context)
            result.fallback_used = True
            return result
        result = self.mock.suggest_fields(context)
        result.fallback_used = True
        return result

    def summarize_workshop(self, context: dict[str, Any]) -> AIResult:
        if not settings.llm_api_key:
            result = self.mock.summarize_workshop(context)
            result.fallback_used = True
            return result
        result = self.mock.summarize_workshop(context)
        result.fallback_used = True
        return result


def get_ai_service() -> AIService:
    mock = MockAIService()
    if settings.ai_mode == 'on':
        return LLMAIService(mock)
    return mock
