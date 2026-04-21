from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.models import CanvasQuestion, CanvasResponse, Participant, Run, User


def _make_session():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return Session(), engine


def _seed_phase1_run(db):
    owner = User(email='advance-owner@example.com', password_hash='hash')
    db.add(owner)
    db.flush()

    run = Run(owner_user_id=owner.id, title='Advance Run', current_phase=1)
    db.add(run)
    db.flush()

    facilitator = Participant(run_id=run.id, user_id=owner.id, role='facilitator')
    db.add(facilitator)
    db.flush()

    problem = CanvasQuestion(key='problem', title='Problem', prompt_template='Describe the problem')
    stakeholders = CanvasQuestion(
        key='stakeholders',
        title='Stakeholders',
        prompt_template='Describe the stakeholders',
    )
    db.add_all([problem, stakeholders])
    db.flush()

    return owner, run, facilitator, problem, stakeholders


def test_advance_phase_is_blocked_when_any_canvas_field_is_empty():
    db, engine = _make_session()
    try:
        owner, run, facilitator, problem, _ = _seed_phase1_run(db)
        db.add(
            CanvasResponse(
                run_id=run.id,
                question_id=problem.id,
                participant_id=facilitator.id,
                cycle=1,
                content='A filled canvas answer',
            )
        )
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_current_user] = lambda: owner
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(f'/projects/{run.id}/advance-phase', headers=headers, json={})

        assert response.status_code == 400
        assert 'fill every canvas field' in response.json()['detail'].lower()
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_advance_phase_succeeds_when_all_canvas_fields_are_filled():
    db, engine = _make_session()
    try:
        owner, run, facilitator, problem, stakeholders = _seed_phase1_run(db)
        db.add_all(
            [
                CanvasResponse(
                    run_id=run.id,
                    question_id=problem.id,
                    participant_id=facilitator.id,
                    cycle=1,
                    content='A filled canvas answer',
                ),
                CanvasResponse(
                    run_id=run.id,
                    question_id=stakeholders.id,
                    participant_id=facilitator.id,
                    cycle=1,
                    content='Another filled canvas answer',
                ),
            ]
        )
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_current_user] = lambda: owner
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(f'/projects/{run.id}/advance-phase', headers=headers, json={})

        assert response.status_code == 200
        assert response.json()['current_phase'] == 2
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
