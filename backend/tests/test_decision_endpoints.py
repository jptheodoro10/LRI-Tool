from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.api.deps import get_current_user, get_db
from app.models import CanvasQuestion, CanvasResponse, Decision, Run, User
from app.models.enums import RunStatus
from app.models.participant import Participant


@pytest.fixture
def db_session():
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def app_client(db_session):
    facilitator = User(
        email='facilitator@example.com',
        password_hash='hash',
    )
    db_session.add(facilitator)
    db_session.flush()

    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: facilitator

    headers = {'Authorization': f'Bearer {create_access_token(str(facilitator.id))}'}

    with TestClient(app) as client:
        yield client, facilitator, headers

    app.dependency_overrides.clear()


def _create_phase5_run(db_session, owner_user_id):
    run = Run(owner_user_id=owner_user_id, title='Test Run', current_phase=5)
    db_session.add(run)
    db_session.flush()
    db_session.add(
        Participant(
            run_id=run.id,
            user_id=owner_user_id,
            role='facilitator',
        )
    )
    db_session.commit()
    db_session.refresh(run)
    return run


def test_phase5_decision_endpoints_are_registered(app_client):
    client, *_ = app_client
    route_paths = {route.path for route in app.routes if hasattr(route, 'path')}

    assert '/projects/{run_id}/decision' in route_paths
    assert '/runs/{run_id}/decision' in route_paths
    assert '/projects/{run_id}/decisions' in route_paths
    assert '/runs/{run_id}/decisions' in route_paths
    assert '/run/{run_id}/decision' in route_paths
    assert '/run/{run_id}/decisions' in route_paths
    assert client.base_url is not None


@pytest.mark.parametrize(
    ('decision', 'expected_phase', 'expected_status', 'expected_cycle', 'expected_payload_decision'),
    [
        ('GO', 5, 'completed', 1, 'GO'),
        ('ABORT', 5, 'completed', 1, 'ABORT'),
        ('PIVOT', 2, 'active', 2, None),
    ],
)
def test_phase5_decision_accepts_go_pivot_and_abort_once(
    app_client,
    db_session,
    decision,
    expected_phase,
    expected_status,
    expected_cycle,
    expected_payload_decision,
):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    response = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': decision},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == run.id
    assert payload['decision'] == expected_payload_decision
    assert payload['current_phase'] == expected_phase
    assert payload['status'] == expected_status
    assert payload['current_cycle'] == expected_cycle

    saved_decision = db_session.scalar(
        select(Decision.decision).where(Decision.run_id == run.id).limit(1)
    )
    assert saved_decision == decision


@pytest.mark.parametrize('path', ['/run/{run_id}/decision', '/run/{run_id}/decisions'])
def test_run_prefix_decision_endpoints_are_accepted(app_client, db_session, path):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    response = client.post(
        path.format(run_id=run.id),
        json={'decision': 'GO'},
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == run.id
    assert payload['decision'] == 'GO'
    assert payload['current_phase'] == 5


def test_phase5_decision_can_be_submitted_via_runs_path(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    response = client.post(
        f'/runs/{run.id}/decision',
        json={'decision': 'ABORT'},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()['decision'] == 'ABORT'


def test_problem_synthesis_can_be_saved_via_patch(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    response = client.patch(
        f'/projects/{run.id}',
        json={'problem_synthesis': 'Condensed synthesis written by the researcher.'},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()['problem_synthesis'] == 'Condensed synthesis written by the researcher.'

    db_session.refresh(run)
    assert run.problem_synthesis == 'Condensed synthesis written by the researcher.'


def test_pivot_allows_follow_up_decision_in_new_cycle(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    pivot = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': 'PIVOT'},
        headers=headers,
    )
    assert pivot.status_code == 200
    assert pivot.json()['current_phase'] == 2
    assert pivot.json()['current_cycle'] == 2

    run.current_phase = 5
    db_session.commit()
    db_session.refresh(run)

    follow_up = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': 'GO'},
        headers=headers,
    )
    assert follow_up.status_code == 200
    payload = follow_up.json()
    assert payload['current_phase'] == 5
    assert payload['current_cycle'] == 2
    assert payload['status'] == 'completed'
    assert payload['decision'] == 'GO'


def test_pivot_clears_problem_synthesis_for_next_cycle(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)
    run.problem_synthesis = 'Synthesis from the previous cycle.'
    db_session.commit()

    pivot = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': 'PIVOT'},
        headers=headers,
    )
    assert pivot.status_code == 200
    assert pivot.json()['current_phase'] == 2
    assert pivot.json()['current_cycle'] == 2

    db_session.refresh(run)
    assert run.problem_synthesis == ''


def test_second_decision_is_rejected(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    first = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': 'GO'},
        headers=headers,
    )
    assert first.status_code == 200

    repeat = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': 'ABORT'},
        headers=headers,
    )
    assert repeat.status_code == 409


def test_pivot_blocks_new_invites_and_still_allows_phase_advance(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    pivot = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': 'PIVOT'},
        headers=headers,
    )
    assert pivot.status_code == 200
    assert pivot.json()['current_phase'] == 2
    assert pivot.json()['current_cycle'] == 2

    invite = client.post(
        f'/projects/{run.id}/invites',
        json={},
        headers=headers,
    )
    assert invite.status_code == 400
    assert 'locked after pivot' in invite.json()['detail'].lower()

    advance = client.post(
        f'/projects/{run.id}/advance-phase',
        json={},
        headers=headers,
    )
    assert advance.status_code == 200
    assert advance.json()['current_phase'] == 3
    assert advance.json()['current_cycle'] == 2


def test_pivot_phase2_canvas_prefills_from_previous_cycle(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)
    facilitator_participant = db_session.scalar(
        select(Participant).where(Participant.run_id == run.id, Participant.role == 'facilitator')
    )
    assert facilitator_participant is not None

    question = CanvasQuestion(
        key='problem',
        title='Problem',
        prompt_template='Describe the problem',
    )
    db_session.add(question)
    db_session.flush()

    db_session.add(
        CanvasResponse(
            run_id=run.id,
            question_id=question.id,
            participant_id=facilitator_participant.id,
            cycle=run.current_cycle,
            content='Existing phase 2 answer',
        )
    )
    db_session.commit()

    pivot = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': 'PIVOT'},
        headers=headers,
    )
    assert pivot.status_code == 200
    assert pivot.json()['current_phase'] == 2
    assert pivot.json()['current_cycle'] == 2

    canvas = client.get(f'/projects/{run.id}/canvas', headers=headers)
    assert canvas.status_code == 200
    items = canvas.json()['items']
    assert len(items) == 1
    assert items[0]['question_key'] == 'problem'
    assert items[0]['response']['content'] == 'Existing phase 2 answer'


def test_legacy_stuck_pivot_state_is_auto_repaired_on_get_run(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)
    run.status = RunStatus.COMPLETED
    db_session.add(
        Decision(
            run_id=run.id,
            cycle=run.current_cycle,
            decision='PIVOT',
            justification='legacy stuck pivot',
        )
    )
    db_session.commit()

    response = client.get(f'/projects/{run.id}', headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload['current_phase'] == 2
    assert payload['current_cycle'] == 2
    assert payload['status'] == 'active'
    assert payload['decision'] is None


def test_legacy_stuck_pivot_state_is_repaired_before_advance_phase(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)
    run.status = RunStatus.COMPLETED
    db_session.add(
        Decision(
            run_id=run.id,
            cycle=run.current_cycle,
            decision='PIVOT',
            justification='legacy stuck pivot',
        )
    )
    db_session.commit()

    response = client.post(f'/projects/{run.id}/advance-phase', headers=headers, json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload['current_phase'] == 3
    assert payload['current_cycle'] == 2


def test_phase2_prefill_uses_latest_non_empty_previous_cycle(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)
    run.current_phase = 2
    run.current_cycle = 3

    facilitator_participant = db_session.scalar(
        select(Participant).where(Participant.run_id == run.id, Participant.role == 'facilitator')
    )
    assert facilitator_participant is not None

    question = CanvasQuestion(
        key='problem',
        title='Problem',
        prompt_template='Describe the problem',
    )
    db_session.add(question)
    db_session.flush()

    db_session.add(
        CanvasResponse(
            run_id=run.id,
            question_id=question.id,
            participant_id=facilitator_participant.id,
            cycle=1,
            content='Answer from older non-empty cycle',
        )
    )
    db_session.commit()

    canvas = client.get(f'/projects/{run.id}/canvas', headers=headers)
    assert canvas.status_code == 200
    items = canvas.json()['items']
    assert len(items) == 1
    assert items[0]['question_key'] == 'problem'
    assert items[0]['response']['content'] == 'Answer from older non-empty cycle'


def test_advancing_phase2_to_phase3_keeps_current_cycle_canvas_prefilled(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)
    run.current_phase = 2
    run.current_cycle = 2

    facilitator_participant = db_session.scalar(
        select(Participant).where(Participant.run_id == run.id, Participant.role == 'facilitator')
    )
    assert facilitator_participant is not None

    question = CanvasQuestion(
        key='problem',
        title='Problem',
        prompt_template='Describe the problem',
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(
        CanvasResponse(
            run_id=run.id,
            question_id=question.id,
            participant_id=facilitator_participant.id,
            cycle=1,
            content='Phase 2 content that must stay visible on phase 3 start',
        )
    )
    db_session.commit()

    advance = client.post(f'/projects/{run.id}/advance-phase', headers=headers, json={})
    assert advance.status_code == 200
    assert advance.json()['current_phase'] == 3

    remaining = db_session.scalars(
        select(CanvasResponse).where(CanvasResponse.run_id == run.id, CanvasResponse.cycle == 2)
    ).all()
    assert len(remaining) == 1
    assert remaining[0].content == 'Phase 2 content that must stay visible on phase 3 start'

    canvas = client.get(f'/projects/{run.id}/canvas', headers=headers)
    assert canvas.status_code == 200
    items = canvas.json()['items']
    assert len(items) == 1
    assert items[0]['response']['content'] == 'Phase 2 content that must stay visible on phase 3 start'


def test_invites_are_listed_with_name_and_link(app_client, db_session, monkeypatch):
    client, facilitator, headers = app_client
    monkeypatch.setattr(settings, 'frontend_public_url', 'https://lri-tool.vercel.app')
    run = _create_phase5_run(db_session, facilitator.id)
    run.current_phase = 2
    db_session.commit()

    created = client.post(
        f'/projects/{run.id}/invites',
        json={'name': 'Alice Johnson'},
        headers=headers,
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload['invite_url'].startswith('https://lri-tool.vercel.app/invite/')

    listed = client.get(f'/projects/{run.id}/invites', headers=headers)
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]['name'] == 'Alice Johnson'
    assert items[0]['status'] == 'pending'
    assert items[0]['invite_url'].startswith('https://lri-tool.vercel.app/invite/')


def test_accepting_used_invite_returns_specific_error(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)
    run.current_phase = 2
    db_session.commit()

    created = client.post(
        f'/projects/{run.id}/invites',
        json={'name': 'Alice Johnson'},
        headers=headers,
    )
    assert created.status_code == 200
    token = created.json()['invite_url'].rsplit('/', 1)[-1]

    first_accept = client.post(
        f'/invites/{token}/accept',
        json={'email': 'alice@example.com'},
    )
    assert first_accept.status_code == 200

    repeat_accept = client.post(
        f'/invites/{token}/accept',
        json={'email': 'alice@example.com'},
    )
    assert repeat_accept.status_code == 400
    assert 'already used' in repeat_accept.json()['detail']


def test_export_pdf_requires_final_go_or_abort_decision(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    response = client.post(
        f'/projects/{run.id}/export/pdf',
        json={},
        headers=headers,
    )
    assert response.status_code == 400
    assert 'final decision' in response.json()['detail'].lower()


def test_export_pdf_contains_problem_synthesis_and_medians_without_comments(app_client, db_session):
    client, facilitator, headers = app_client
    run = _create_phase5_run(db_session, facilitator.id)

    facilitator_participant = db_session.scalar(
        select(Participant).where(Participant.run_id == run.id, Participant.role == 'facilitator')
    )
    assert facilitator_participant is not None

    problem_question = CanvasQuestion(
        key='problem',
        title='Problem',
        prompt_template='Describe the practical problem',
    )
    stakeholders_question = CanvasQuestion(
        key='stakeholders',
        title='Stakeholders',
        prompt_template='Describe the context',
    )
    db_session.add_all([problem_question, stakeholders_question])
    db_session.flush()

    db_session.add_all(
        [
            CanvasResponse(
                run_id=run.id,
                question_id=problem_question.id,
                participant_id=facilitator_participant.id,
                cycle=run.current_cycle,
                content='Manual process causes recurring data delays.',
            ),
            CanvasResponse(
                run_id=run.id,
                question_id=stakeholders_question.id,
                participant_id=facilitator_participant.id,
                cycle=run.current_cycle,
                content='Product, support, and operations teams are impacted.',
            ),
        ]
    )
    db_session.commit()

    patch_response = client.patch(
        f'/projects/{run.id}',
        json={'problem_synthesis': 'Researchers synthesized the problem as a recurring operational bottleneck that merits immediate investigation.'},
        headers=headers,
    )
    assert patch_response.status_code == 200

    score_payloads = [
        {
            'participant_id': facilitator_participant.id,
            'metric_key': 'impact',
            'value': 7,
            'comment': 'This comment must not appear in PDF.',
        },
        {
            'participant_id': facilitator_participant.id,
            'metric_key': 'alignment',
            'value': 6,
            'comment': 'Alignment comment should be excluded.',
        },
        {
            'participant_id': facilitator_participant.id,
            'metric_key': 'feasibility',
            'value': 5,
            'comment': 'Feasibility comment should be excluded.',
        },
    ]
    for payload in score_payloads:
        score_response = client.post(
            f'/projects/{run.id}/scores',
            json=payload,
            headers=headers,
        )
        assert score_response.status_code == 200

    decision_response = client.post(
        f'/projects/{run.id}/decision',
        json={'decision': 'GO'},
        headers=headers,
    )
    assert decision_response.status_code == 200

    exported = client.post(
        f'/projects/{run.id}/export/pdf',
        json={},
        headers=headers,
    )
    assert exported.status_code == 200
    payload = exported.json()

    file_path = Path(payload['file_path'])
    assert file_path.exists()

    pdf_text = file_path.read_bytes().decode('latin-1', errors='ignore')
    normalized_text = pdf_text.replace('\\(', '(').replace('\\)', ')')
    assert 'Workshop date: ' in normalized_text
    assert 'Formulated Problem' in normalized_text
    assert 'For the practical problem (what/how/why)' in normalized_text
    assert 'Manual process causes recurring data delays.' in normalized_text
    assert 'Assessment Medians' in normalized_text
    assert 'Value: 7.00 median (1 responses)' in normalized_text
    assert 'Applicability: 6.00 median (1 responses)' in normalized_text
    assert 'Feasibility: 5.00 median (1 responses)' in normalized_text
    assert 'Decision' in normalized_text
    assert 'GO' in normalized_text
    assert 'Researchers synthesized the problem as a recurring' in normalized_text
    assert 'operational bottleneck' in normalized_text
    assert 'merits immediate investigatio' in normalized_text
    assert 'The formulated problem received a' not in normalized_text
    assert 'This comment must not appear in PDF.' not in normalized_text
    assert 'Alignment comment should be excluded.' not in normalized_text
    assert 'Feasibility comment should be excluded.' not in normalized_text
