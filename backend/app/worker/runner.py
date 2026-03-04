from datetime import datetime, timedelta
import time

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AIJob, FieldSuggestion, JobStatus, JobType, PhaseEntry, Project, WorkshopSummary
from app.services.ai_service import get_ai_service


def process_suggest_job(db, job: AIJob):
    ai = get_ai_service()
    result = ai.suggest_fields(job.input_payload)

    for item in result.payload.get('suggestions', []):
        suggestion = FieldSuggestion(
            project_id=job.project_id,
            cycle_number=job.cycle_number,
            phase=job.input_payload.get('phase', 'F1'),
            target_field=item['target_field'],
            source_field=item.get('source_field', job.input_payload.get('changed_field', '')),
            suggested_text=item['suggested_text'],
            confidence=item.get('confidence'),
            rationale=item.get('rationale'),
            job_id=job.id,
        )
        db.add(suggestion)

    job.output_payload = result.payload
    job.fallback_used = result.fallback_used


def process_summarize_job(db, job: AIJob):
    ai = get_ai_service()
    project = db.get(Project, job.project_id)
    entries = db.scalars(
        select(PhaseEntry).where(PhaseEntry.project_id == job.project_id, PhaseEntry.cycle_number == job.cycle_number)
    ).all()
    highlights = [f'{e.phase}:{e.field_key}' for e in entries[:8]]
    context = {
        'project_title': project.title if project else 'Project',
        'decision': job.input_payload.get('decision', 'undecided'),
        'highlights': highlights,
    }
    result = ai.summarize_workshop(context)
    summary = WorkshopSummary(
        project_id=job.project_id,
        cycle_number=job.cycle_number,
        summary_text=result.payload.get('summary_text', ''),
        highlights_json={'highlights': result.payload.get('highlights', [])},
        job_id=job.id,
    )
    db.add(summary)
    job.output_payload = result.payload
    job.fallback_used = result.fallback_used


def run_forever():
    while True:
        with SessionLocal() as db:
            job = db.scalars(select(AIJob).where(AIJob.status == JobStatus.PENDING).order_by(AIJob.created_at)).first()
            if not job:
                time.sleep(1)
                continue

            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            db.commit()

            try:
                if job.job_type == JobType.SUGGEST:
                    process_suggest_job(db, job)
                else:
                    process_summarize_job(db, job)

                if job.started_at and datetime.utcnow() - job.started_at > timedelta(seconds=settings.ai_job_timeout_seconds):
                    job.status = JobStatus.TIMEOUT
                else:
                    job.status = JobStatus.COMPLETED
            except Exception as exc:  # noqa: BLE001
                job.status = JobStatus.FAILED
                job.error_message = str(exc)

            job.finished_at = datetime.utcnow()
            db.commit()


if __name__ == '__main__':
    run_forever()
