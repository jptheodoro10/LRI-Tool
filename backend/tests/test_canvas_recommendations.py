from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.api.deps import get_db
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


def _seed_owner_run(db, *, phase: int = 1, ai_mode_enabled: bool = True):
    owner = User(email=f'owner-phase-{phase}@example.com', password_hash='hash')
    db.add(owner)
    db.flush()

    run = Run(
        owner_user_id=owner.id,
        title='Recommendation Run',
        current_phase=phase,
        ai_mode_enabled=ai_mode_enabled,
    )
    db.add(run)
    db.flush()

    facilitator = Participant(run_id=run.id, user_id=owner.id, role='facilitator')
    db.add(facilitator)
    db.flush()
    return owner, run, facilitator


def test_canvas_recommendations_generate_for_blank_fields_in_phase1(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    db, engine = _make_session()
    try:
        owner, run, facilitator = _seed_owner_run(db, phase=1, ai_mode_enabled=True)
        problem = CanvasQuestion(
            key='problem',
            title='Problem',
            prompt_template='Describe the problem',
        )
        stakeholders = CanvasQuestion(
            key='stakeholders',
            title='Stakeholders',
            prompt_template='Describe the stakeholders',
        )
        db.add_all([problem, stakeholders])
        db.flush()

        db.add(
            CanvasResponse(
                run_id=run.id,
                question_id=problem.id,
                participant_id=facilitator.id,
                cycle=1,
                content='Teams are losing time with unstable deployment pipelines.',
            )
        )
        db.add(
            CanvasResponse(
                run_id=run.id,
                question_id=stakeholders.id,
                participant_id=facilitator.id,
                cycle=1,
                content='   ',
            )
        )
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/canvas/recommendations',
                headers=headers,
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload['filled_count'] == 1
        assert payload['empty_count'] == 1
        assert payload['generated_count'] == 1
        assert 'stakeholders' in payload['suggestions']
        assert payload['suggestions']['stakeholders']['status'] == 'succeeded'
        assert payload['suggestions']['stakeholders']['suggested_text']
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_single_canvas_recommendation_generates_for_requested_blank_field(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    db, engine = _make_session()
    try:
        owner, run, facilitator = _seed_owner_run(db, phase=1, ai_mode_enabled=True)
        problem = CanvasQuestion(
            key='problem',
            title='Problem',
            prompt_template='Describe the problem',
        )
        stakeholders = CanvasQuestion(
            key='stakeholders',
            title='Stakeholders',
            prompt_template='Describe the stakeholders',
        )
        db.add_all([problem, stakeholders])
        db.flush()

        db.add(
            CanvasResponse(
                run_id=run.id,
                question_id=problem.id,
                participant_id=facilitator.id,
                cycle=1,
                content='Teams are losing time with unstable deployment pipelines.',
            )
        )
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/canvas/stakeholders/recommendation',
                headers=headers,
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload['question_key'] == 'stakeholders'
        assert payload['status'] == 'succeeded'
        assert payload['suggested_text']
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_single_canvas_recommendation_requires_empty_field(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    db, engine = _make_session()
    try:
        owner, run, facilitator = _seed_owner_run(db, phase=1, ai_mode_enabled=True)
        problem = CanvasQuestion(
            key='problem',
            title='Problem',
            prompt_template='Describe the problem',
        )
        stakeholders = CanvasQuestion(
            key='stakeholders',
            title='Stakeholders',
            prompt_template='Describe the stakeholders',
        )
        db.add_all([problem, stakeholders])
        db.flush()

        db.add_all(
            [
                CanvasResponse(
                    run_id=run.id,
                    question_id=problem.id,
                    participant_id=facilitator.id,
                    cycle=1,
                    content='Teams are losing time with unstable deployment pipelines.',
                ),
                CanvasResponse(
                    run_id=run.id,
                    question_id=stakeholders.id,
                    participant_id=facilitator.id,
                    cycle=1,
                    content='Release engineers and product teams.',
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
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/canvas/stakeholders/recommendation',
                headers=headers,
            )

        assert response.status_code == 400
        assert 'empty fields' in response.json()['detail'].lower()
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_canvas_recommendations_are_restricted_to_phase1(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    db, engine = _make_session()
    try:
        owner, run, facilitator = _seed_owner_run(db, phase=2, ai_mode_enabled=True)
        problem = CanvasQuestion(
            key='problem',
            title='Problem',
            prompt_template='Describe the problem',
        )
        db.add(problem)
        db.flush()
        db.add(
            CanvasResponse(
                run_id=run.id,
                question_id=problem.id,
                participant_id=facilitator.id,
                cycle=1,
                content='Existing content',
            )
        )
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/canvas/recommendations',
                headers=headers,
            )

        assert response.status_code == 400
        assert 'phase 1' in response.json()['detail'].lower()
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_phase3_overview_generates_when_canvas_is_complete(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    db, engine = _make_session()
    try:
        owner, run, facilitator = _seed_owner_run(db, phase=3, ai_mode_enabled=True)
        questions = [
            CanvasQuestion(key='problem', title='Problem', prompt_template='Describe the problem'),
            CanvasQuestion(key='stakeholders', title='Stakeholders', prompt_template='Describe the stakeholders'),
        ]
        db.add_all(questions)
        db.flush()

        db.add_all(
            [
                CanvasResponse(
                    run_id=run.id,
                    question_id=questions[0].id,
                    participant_id=facilitator.id,
                    cycle=1,
                    content='Deployment failures are delaying product releases.',
                ),
                CanvasResponse(
                    run_id=run.id,
                    question_id=questions[1].id,
                    participant_id=facilitator.id,
                    cycle=1,
                    content='Engineering managers, release engineers, and product teams are directly affected.',
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
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/canvas/overview',
                headers=headers,
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload['generated_count'] == 2
        assert payload['field_count'] == 2
        assert payload['overviews']['problem']
        assert payload['overviews']['stakeholders']
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_phase3_single_canvas_overview_generates_for_requested_field(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    db, engine = _make_session()
    try:
        owner, run, facilitator = _seed_owner_run(db, phase=3, ai_mode_enabled=True)
        questions = [
            CanvasQuestion(key='problem', title='Problem', prompt_template='Describe the problem'),
            CanvasQuestion(key='stakeholders', title='Stakeholders', prompt_template='Describe the stakeholders'),
        ]
        db.add_all(questions)
        db.flush()

        db.add_all(
            [
                CanvasResponse(
                    run_id=run.id,
                    question_id=questions[0].id,
                    participant_id=facilitator.id,
                    cycle=1,
                    content='Deployment failures are delaying product releases.',
                ),
                CanvasResponse(
                    run_id=run.id,
                    question_id=questions[1].id,
                    participant_id=facilitator.id,
                    cycle=1,
                    content='Engineering managers, release engineers, and product teams are directly affected.',
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
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/canvas/problem/overview',
                headers=headers,
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload['question_key'] == 'problem'
        assert payload['overview_text']
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_phase3_overview_requires_complete_canvas(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    db, engine = _make_session()
    try:
        owner, run, facilitator = _seed_owner_run(db, phase=3, ai_mode_enabled=True)
        problem = CanvasQuestion(
            key='problem',
            title='Problem',
            prompt_template='Describe the problem',
        )
        stakeholders = CanvasQuestion(
            key='stakeholders',
            title='Stakeholders',
            prompt_template='Describe the stakeholders',
        )
        db.add_all([problem, stakeholders])
        db.flush()

        db.add(
            CanvasResponse(
                run_id=run.id,
                question_id=problem.id,
                participant_id=facilitator.id,
                cycle=1,
                content='Only one filled answer.',
            )
        )
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/canvas/overview',
                headers=headers,
            )

        assert response.status_code == 400
        assert 'fill every canvas field' in response.json()['detail'].lower()
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_phase3_overview_is_restricted_to_phase3(monkeypatch):
    monkeypatch.setattr('app.services.llm_client.settings.llm_api_key', '')
    db, engine = _make_session()
    try:
        owner, run, facilitator = _seed_owner_run(db, phase=2, ai_mode_enabled=True)
        problem = CanvasQuestion(
            key='problem',
            title='Problem',
            prompt_template='Describe the problem',
        )
        db.add(problem)
        db.flush()
        db.add(
            CanvasResponse(
                run_id=run.id,
                question_id=problem.id,
                participant_id=facilitator.id,
                cycle=1,
                content='Existing content',
            )
        )
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/canvas/overview',
                headers=headers,
            )

        assert response.status_code == 400
        assert 'phase 3' in response.json()['detail'].lower()
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
