from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import AISuggestionStatus, Participant, Run, User
from app.repositories import AISuggestionRepository, CanvasRepository, ParticipantRepository, RunRepository
from app.services.ai_service import AISuggestionService
from app.services.canvas_service import CanvasService


def _make_session():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session(), engine


def _seed_run_with_facilitator(db, *, phase: int):
    user = User(email=f'owner-{phase}@example.com', password_hash='hash')
    db.add(user)
    db.flush()

    run = Run(owner_user_id=user.id, title=f'Run phase {phase}', current_phase=phase, ai_mode_enabled=True)
    db.add(run)
    db.flush()

    facilitator = Participant(run_id=run.id, user_id=user.id, role='facilitator')
    db.add(facilitator)
    db.flush()
    return run, facilitator


def test_ai_suggestions_are_not_generated_outside_phase1():
    db, engine = _make_session()
    try:
        run, facilitator = _seed_run_with_facilitator(db, phase=2)
        canvas_repo = CanvasRepository(db)
        q1 = canvas_repo.create_question('problem', 'Problem', 'Describe problem')
        canvas_repo.create_question('stakeholders', 'Stakeholders', 'Describe stakeholders')
        canvas_repo.upsert_response(
            run_id=run.id,
            question_id=q1.id,
            participant_id=facilitator.id,
            cycle=1,
            content='Some context',
        )

        AISuggestionService(db).refresh_suggestions_for_run(run.id)
        rows = AISuggestionRepository(db).list_by_run(run.id, cycle=1)
        assert rows == []
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_canvas_view_hides_suggestions_outside_phase1_and_keeps_in_phase1():
    db, engine = _make_session()
    try:
        run, facilitator = _seed_run_with_facilitator(db, phase=2)
        canvas_repo = CanvasRepository(db)
        ai_repo = AISuggestionRepository(db)
        q1 = canvas_repo.create_question('problem', 'Problem', 'Describe problem')
        canvas_repo.upsert_response(
            run_id=run.id,
            question_id=q1.id,
            participant_id=facilitator.id,
            cycle=1,
            content='Phase2 content',
        )
        ai_repo.upsert(
            run_id=run.id,
            question_id=q1.id,
            cycle=1,
            status=AISuggestionStatus.SUCCEEDED,
            context_hash='ctx',
            output={'text': 'AI suggestion'},
            error_message=None,
        )

        svc = CanvasService(
            run_repo=RunRepository(db),
            participant_repo=ParticipantRepository(db),
            canvas_repo=canvas_repo,
            ai_repo=ai_repo,
        )
        phase2_view = svc.get_canvas_view(run.id)
        assert phase2_view['items'][0]['suggestion'] is None

        run.current_phase = 1
        db.flush()
        phase1_view = svc.get_canvas_view(run.id)
        assert phase1_view['items'][0]['suggestion'] is not None
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
