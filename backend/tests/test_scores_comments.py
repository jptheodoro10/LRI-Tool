from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from fastapi.testclient import TestClient

from app.api.deps import get_db, get_optional_current_user
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.models import Invite, InviteStatus, Participant, Run, User


def _session_factory():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return engine, Session


def test_scores_include_phase4_comments_and_phase5_comment_list():
    engine, Session = _session_factory()
    db = Session()
    try:
        owner = User(email='owner@example.com', password_hash='hash')
        db.add(owner)
        db.flush()

        run = Run(owner_user_id=owner.id, title='Comments run', current_phase=4, current_cycle=1)
        db.add(run)
        db.flush()

        db.add(
            Participant(
                run_id=run.id,
                user_id=owner.id,
                role='facilitator',
            )
        )
        p1 = Participant(run_id=run.id, email='ana@example.com', role='collaborator')
        p2 = Participant(run_id=run.id, email='bruno@example.com', role='collaborator')
        db.add_all([p1, p2])
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_optional_current_user] = lambda: owner

        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            payloads = [
                {'participant_id': p1.id, 'metric_key': 'impact', 'value': 6, 'comment': 'Very valuable.'},
                {'participant_id': p1.id, 'metric_key': 'alignment', 'value': 5, 'comment': 'Fits the context.'},
                {'participant_id': p1.id, 'metric_key': 'feasibility', 'value': 4, 'comment': ''},
                {'participant_id': p2.id, 'metric_key': 'impact', 'value': 7, 'comment': 'Strong impact.'},
                {'participant_id': p2.id, 'metric_key': 'alignment', 'value': 6, 'comment': 'Applicable in practice.'},
                {'participant_id': p2.id, 'metric_key': 'feasibility', 'value': 5, 'comment': 'Feasible with resources.'},
            ]
            for payload in payloads:
                response = client.post(
                    f'/projects/{run.id}/scores',
                    json=payload,
                    headers=headers,
                )
                assert response.status_code == 200

            participant_scores = client.get(
                f'/projects/{run.id}/scores?participant_id={p1.id}',
                headers=headers,
            )
            assert participant_scores.status_code == 200
            participant_payload = participant_scores.json()
            assert participant_payload['participant_comments']['impact'] == 'Very valuable.'
            assert participant_payload['participant_comments']['alignment'] == 'Fits the context.'
            assert 'feasibility' not in participant_payload['participant_comments']

            aggregated = client.get(f'/projects/{run.id}/scores', headers=headers)
            assert aggregated.status_code == 200
            comments = aggregated.json()['comments']
            assert len(comments) == 2
            labels = {item['participant_label'] for item in comments}
            assert labels == {f'Participant {p1.id}', f'Participant {p2.id}'}
            ana = next(item for item in comments if item['participant_id'] == p1.id)
            assert ana['comments']['impact'] == 'Very valuable.'
            assert ana['comments']['alignment'] == 'Fits the context.'
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_comment_labels_prefer_invite_participant_name():
    engine, Session = _session_factory()
    db = Session()
    try:
        owner = User(email='owner2@example.com', password_hash='hash')
        db.add(owner)
        db.flush()

        run = Run(owner_user_id=owner.id, title='Named invite run', current_phase=4, current_cycle=1)
        db.add(run)
        db.flush()

        db.add(Participant(run_id=run.id, user_id=owner.id, role='facilitator'))
        participant = Participant(run_id=run.id, email='participant@example.com', role='collaborator')
        db.add(participant)
        db.flush()

        db.add(
            Invite(
                run_id=run.id,
                token_hash='hash-token-1',
                public_token='public-token-1',
                invitee_name='Legacy Name',
                participant_name='marina silva',
                role='collaborator',
                status=InviteStatus.ACCEPTED,
                accepted_participant_id=participant.id,
                expires_at=run.created_at,
            )
        )
        db.commit()

        def _get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = _get_db
        app.dependency_overrides[get_optional_current_user] = lambda: owner
        headers = {'Authorization': f'Bearer {create_access_token(str(owner.id))}'}

        with TestClient(app) as client:
            response = client.post(
                f'/projects/{run.id}/scores',
                json={
                    'participant_id': participant.id,
                    'metric_key': 'impact',
                    'value': 6,
                    'comment': 'Nome deve aparecer',
                },
                headers=headers,
            )
            assert response.status_code == 200

            listed = client.get(f'/projects/{run.id}/scores', headers=headers)
            assert listed.status_code == 200
            comments = listed.json()['comments']
            assert len(comments) == 1
            assert comments[0]['participant_label'] == 'Marina Silva'
    finally:
        app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
