from __future__ import annotations

from datetime import datetime
import hashlib
import json

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import AISuggestionStatus
from app.repositories import AISuggestionRepository, CanvasRepository, RunRepository
from app.services.llm_client import get_llm_client


class AISuggestionService:
    def __init__(self, db: Session):
        self.db = db
        self.run_repo = RunRepository(db)
        self.canvas_repo = CanvasRepository(db)
        self.ai_repo = AISuggestionRepository(db)
        self.llm_client = get_llm_client()

    def _response_cycle_for_run(self, run) -> int:
        if run.current_phase == 2 and run.current_cycle > 1:
            return max(1, run.current_cycle - 1)
        return run.current_cycle

    def compute_context_hash(self, run_id: int, cycle: int) -> str:
        responses = self.canvas_repo.list_responses_by_run(run_id, cycle=cycle)
        questions_by_id = {q.id: q.key for q in self.canvas_repo.list_questions()}
        payload = [
            {
                'question_key': questions_by_id.get(r.question_id, str(r.question_id)),
                'content': r.content,
                'participant_id': r.participant_id,
            }
            for r in responses
        ]
        payload.sort(key=lambda item: item['question_key'])
        serialized = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

    def refresh_suggestions_for_run(self, run_id: int) -> None:
        run = self.run_repo.get(run_id)
        if run is None or not run.ai_mode_enabled:
            return
        if run.current_phase != 1:
            return

        cycle = self._response_cycle_for_run(run)
        context_hash = self.compute_context_hash(run_id, cycle=cycle)
        unanswered_questions = self.canvas_repo.list_unanswered_questions(run_id, cycle=cycle)
        responses = self.canvas_repo.list_responses_by_run(run_id, cycle=cycle)
        question_map = {q.id: q.key for q in self.canvas_repo.list_questions()}

        context_lines = []
        for response in responses:
            key = question_map.get(response.question_id, str(response.question_id))
            context_lines.append(f'{key}: {response.content}')
        context_text = '\n'.join(context_lines).strip() or 'No responses yet.'

        for question in unanswered_questions:
            existing = self.ai_repo.get(run_id=run_id, question_id=question.id, cycle=cycle)
            if existing and existing.context_hash == context_hash and existing.status == AISuggestionStatus.SUCCEEDED:
                continue

            if existing and existing.context_hash != context_hash and existing.status in {
                AISuggestionStatus.QUEUED,
                AISuggestionStatus.RUNNING,
            }:
                self.ai_repo.upsert(
                    run_id=run_id,
                    question_id=question.id,
                    cycle=cycle,
                    status=AISuggestionStatus.STALE,
                    context_hash=existing.context_hash,
                    output=existing.output,
                    error_message=existing.error_message,
                )

            self.ai_repo.upsert(
                run_id=run_id,
                question_id=question.id,
                cycle=cycle,
                status=AISuggestionStatus.QUEUED,
                context_hash=context_hash,
                output=None,
                error_message=None,
            )
            self.ai_repo.upsert(
                run_id=run_id,
                question_id=question.id,
                cycle=cycle,
                status=AISuggestionStatus.RUNNING,
                context_hash=context_hash,
                output=None,
                error_message=None,
            )

            prompt = (
                'You are assisting a Lean Research Inception workshop. '
                f'Generate a concise suggestion for the unanswered canvas "{question.key}".\n\n'
                f'Current run context:\n{context_text}'
            )

            try:
                suggestion_text = self.llm_client.generate(prompt)
                self.ai_repo.upsert(
                    run_id=run_id,
                    question_id=question.id,
                    cycle=cycle,
                    status=AISuggestionStatus.SUCCEEDED,
                    context_hash=context_hash,
                    output={'text': suggestion_text, 'question_key': question.key},
                    error_message=None,
                )
            except Exception as exc:  # noqa: BLE001
                self.ai_repo.upsert(
                    run_id=run_id,
                    question_id=question.id,
                    cycle=cycle,
                    status=AISuggestionStatus.FAILED,
                    context_hash=context_hash,
                    output=None,
                    error_message=str(exc),
                )

        # Keep timestamps monotonic for consumers.
        now = datetime.utcnow()
        for suggestion in self.ai_repo.list_by_run(run_id, cycle=cycle):
            suggestion.updated_at = now
        self.db.flush()


def refresh_suggestions_background(run_id: int) -> None:
    with SessionLocal() as db:
        service = AISuggestionService(db)
        service.refresh_suggestions_for_run(run_id)
        db.commit()
