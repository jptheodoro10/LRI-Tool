from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, create_invite_token, hash_token, verify_password
from app.db.session import get_db
from app.models import (
    AIJob,
    ActorType,
    AssessmentCriterion,
    AssessmentRespondent,
    AssessmentScore,
    AssessmentSession,
    Decision,
    DecisionType,
    Export,
    Invite,
    JobStatus,
    JobType,
    Participant,
    Phase,
    PhaseEntry,
    Project,
    ProjectCycle,
    User,
    WorkshopSummary,
)
from app.schemas.common import (
    AIJobStatusOut,
    AssessmentScoreRequest,
    AssessmentStartRequest,
    DecisionRequest,
    ExportOut,
    InviteOut,
    JoinInviteRequest,
    JoinInviteResponse,
    LoginRequest,
    PhaseEntryPatch,
    PhaseEntryPatchResponse,
    ProjectCreate,
    ProjectOut,
    SummaryGenerateResponse,
    TokenResponse,
)
from app.services.pdf_service import build_pdf

router = APIRouter()

PHASE_ORDER = [Phase.F1, Phase.F2, Phase.F3, Phase.F4, Phase.F5]


def ensure_owner(project: Project | None, user: User):
    if not project or project.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail='Project not found')


@router.post('/auth/login', response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get('/auth/me')
def me(current_user: User = Depends(get_current_user)):
    return {'id': current_user.id, 'email': current_user.email}


@router.post('/projects', response_model=ProjectOut)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = Project(owner_user_id=current_user.id, title=payload.title, current_phase=Phase.F1, current_cycle=1)
    db.add(project)
    db.flush()
    db.add(ProjectCycle(project_id=project.id, cycle_number=1))
    db.commit()
    db.refresh(project)
    return project


@router.get('/projects', response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    projects = db.scalars(select(Project).where(Project.owner_user_id == current_user.id).order_by(Project.created_at.desc())).all()
    return projects


@router.get('/projects/{project_id}', response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)
    return project


@router.post('/projects/{project_id}/advance-phase', response_model=ProjectOut)
def advance_phase(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)
    idx = PHASE_ORDER.index(project.current_phase)
    if idx >= len(PHASE_ORDER) - 1:
        return project
    project.current_phase = PHASE_ORDER[idx + 1]
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project


@router.post('/projects/{project_id}/invites', response_model=InviteOut)
def create_invite(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)
    if project.current_phase == Phase.F1:
        raise HTTPException(status_code=400, detail='Invites allowed from phase F2')

    raw_token = create_invite_token()
    invite = Invite(
        project_id=project_id,
        token_hash=hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(days=settings.invite_expiration_days),
    )
    db.add(invite)
    db.commit()
    return InviteOut(invite_url=f'http://localhost:5173/invite/{raw_token}', expires_at=invite.expires_at)


@router.get('/invite/{token}')
def inspect_invite(token: str, db: Session = Depends(get_db)):
    invite = db.scalar(select(Invite).where(Invite.token_hash == hash_token(token)))
    if not invite or invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail='Invalid or expired invite')
    return {'project_id': invite.project_id, 'expires_at': invite.expires_at}


@router.post('/invite/{token}/join', response_model=JoinInviteResponse)
def join_invite(token: str, payload: JoinInviteRequest, db: Session = Depends(get_db)):
    if not payload.consent:
        raise HTTPException(status_code=400, detail='Consent is required')

    invite = db.scalar(select(Invite).where(Invite.token_hash == hash_token(token)))
    if not invite or invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=404, detail='Invalid or expired invite')

    participant = Participant(
        project_id=invite.project_id,
        invite_id=invite.id,
        name=payload.name,
        company=payload.company,
        consent_accepted_at=datetime.utcnow(),
    )
    invite.used_at = datetime.utcnow()
    db.add(participant)
    db.commit()
    db.refresh(participant)
    return JoinInviteResponse(participant_id=participant.id, project_id=participant.project_id)


@router.patch('/projects/{project_id}/phases/{phase}/entries', response_model=PhaseEntryPatchResponse)
def patch_phase_entry(project_id: int, phase: Phase, payload: PhaseEntryPatch, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')

    if PHASE_ORDER.index(phase) > PHASE_ORDER.index(project.current_phase):
        raise HTTPException(status_code=400, detail='Phase not unlocked')

    actor_type = ActorType(payload.actor_type)

    if actor_type == ActorType.PARTICIPANT:
        participant = db.get(Participant, payload.actor_id)
        if not participant or participant.project_id != project_id:
            raise HTTPException(status_code=403, detail='Invalid participant')

    entry = db.scalar(
        select(PhaseEntry).where(
            PhaseEntry.project_id == project_id,
            PhaseEntry.cycle_number == project.current_cycle,
            PhaseEntry.phase == phase,
            PhaseEntry.actor_type == actor_type,
            PhaseEntry.actor_id == payload.actor_id,
            PhaseEntry.field_key == payload.field_key,
        )
    )

    if not entry:
        entry = PhaseEntry(
            project_id=project_id,
            cycle_number=project.current_cycle,
            phase=phase,
            actor_type=actor_type,
            actor_id=payload.actor_id,
            field_key=payload.field_key,
            content=payload.content,
            entry_version=1,
        )
        db.add(entry)
    else:
        entry.content = payload.content
        entry.entry_version += 1
        entry.updated_at = datetime.utcnow()

    db.flush()

    ai_job_id = None
    if phase in [Phase.F1, Phase.F2, Phase.F3]:
        job = AIJob(
            project_id=project_id,
            cycle_number=project.current_cycle,
            actor_type=actor_type,
            actor_id=payload.actor_id,
            job_type=JobType.SUGGEST,
            status=JobStatus.PENDING,
            input_payload={
                'project_id': project_id,
                'phase': phase.value,
                'changed_field': payload.field_key,
                'content': payload.content,
                'actor_id': payload.actor_id,
            },
        )
        db.add(job)
        db.flush()
        ai_job_id = job.id

    db.commit()
    return PhaseEntryPatchResponse(entry_version=entry.entry_version, ai_job_id=ai_job_id)


@router.get('/ai/jobs/{job_id}', response_model=AIJobStatusOut)
def get_ai_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.get(AIJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    project = db.get(Project, job.project_id)
    ensure_owner(project, current_user)
    return AIJobStatusOut(
        id=job.id,
        status=job.status.value,
        job_type=job.job_type.value,
        fallback_used=job.fallback_used,
        error_message=job.error_message,
    )


@router.get('/projects/{project_id}/phases/{phase}/suggestions')
def get_field_suggestions(
    project_id: int,
    phase: Phase,
    field: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)
    rows = db.execute(
        select(AIJob.output_payload)
        .where(AIJob.project_id == project_id, AIJob.job_type == JobType.SUGGEST, AIJob.status == JobStatus.COMPLETED)
        .order_by(AIJob.finished_at.desc())
    ).all()
    suggestions = []
    for row in rows:
        payload = row[0] or {}
        for s in payload.get('suggestions', []):
            if s.get('target_field') == field:
                suggestions.append(s)
    return {'suggestions': suggestions[:3]}


@router.post('/projects/{project_id}/assessment/start')
def start_assessment(
    project_id: int,
    payload: AssessmentStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)
    if project.current_phase != Phase.F4:
        raise HTTPException(status_code=400, detail='Assessment starts in F4 only')

    session = AssessmentSession(project_id=project_id, cycle_number=project.current_cycle, status='open')
    db.add(session)
    db.flush()
    db.add(AssessmentRespondent(session_id=session.id, actor_type=ActorType.RESEARCHER, actor_id=current_user.id))
    for participant_id in payload.participants:
        db.add(AssessmentRespondent(session_id=session.id, actor_type=ActorType.PARTICIPANT, actor_id=participant_id))
    db.commit()
    return {'session_id': session.id}


@router.post('/projects/{project_id}/assessment/score')
def submit_score(project_id: int, payload: AssessmentScoreRequest, db: Session = Depends(get_db)):
    session = db.scalar(
        select(AssessmentSession)
        .where(AssessmentSession.project_id == project_id)
        .order_by(AssessmentSession.id.desc())
    )
    if not session:
        raise HTTPException(status_code=404, detail='Assessment session not found')

    if payload.score < 1 or payload.score > 7:
        raise HTTPException(status_code=400, detail='Score must be between 1 and 7')

    exists = db.scalar(
        select(AssessmentScore).where(
            AssessmentScore.session_id == session.id,
            AssessmentScore.actor_type == ActorType(payload.actor_type),
            AssessmentScore.actor_id == payload.actor_id,
            AssessmentScore.criterion == AssessmentCriterion(payload.criterion),
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail='Criterion already submitted for actor')

    db.add(
        AssessmentScore(
            session_id=session.id,
            actor_type=ActorType(payload.actor_type),
            actor_id=payload.actor_id,
            criterion=AssessmentCriterion(payload.criterion),
            score=payload.score,
            justification=payload.justification,
        )
    )
    db.commit()
    return {'ok': True}


@router.get('/projects/{project_id}/assessment/consolidated')
def consolidated_assessment(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)
    session = db.scalar(
        select(AssessmentSession)
        .where(AssessmentSession.project_id == project_id)
        .order_by(AssessmentSession.id.desc())
    )
    if not session:
        raise HTTPException(status_code=404, detail='Assessment session not found')

    totals = {}
    for criterion in AssessmentCriterion:
        rows = db.scalars(
            select(AssessmentScore.score).where(
                AssessmentScore.session_id == session.id,
                AssessmentScore.criterion == criterion,
            )
        ).all()
        if rows:
            avg = sum(rows) / len(rows)
        else:
            avg = 0
        totals[criterion.value] = {
            'avg': avg,
            'count': len(rows),
            'distribution': {str(n): rows.count(n) for n in range(1, 8)},
        }

    required = db.scalars(select(AssessmentRespondent).where(AssessmentRespondent.session_id == session.id)).all()
    completed = db.execute(
        select(AssessmentScore.actor_type, AssessmentScore.actor_id, func.count(AssessmentScore.id))
        .where(AssessmentScore.session_id == session.id)
        .group_by(AssessmentScore.actor_type, AssessmentScore.actor_id)
    ).all()
    done_map = {(str(a), b): c for a, b, c in completed}
    all_done = all(done_map.get((r.actor_type.value, r.actor_id), 0) >= 3 for r in required)

    return {'criteria': totals, 'all_done': all_done, 'required_respondents': len(required)}


@router.post('/projects/{project_id}/decision')
def register_decision(
    project_id: int,
    payload: DecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)
    decision_type = DecisionType(payload.decision)

    db.add(
        Decision(
            project_id=project_id,
            cycle_number=project.current_cycle,
            decision=decision_type,
            justification=payload.justification,
        )
    )

    if decision_type == DecisionType.PIVOT:
        current_cycle = db.scalar(
            select(ProjectCycle).where(
                ProjectCycle.project_id == project_id,
                ProjectCycle.cycle_number == project.current_cycle,
            )
        )
        if current_cycle:
            current_cycle.closed_at = datetime.utcnow()
            current_cycle.close_reason = decision_type
        project.current_cycle += 1
        project.current_phase = Phase.F2
        db.add(ProjectCycle(project_id=project_id, cycle_number=project.current_cycle))

    db.commit()
    return {'ok': True, 'project_cycle': project.current_cycle, 'phase': project.current_phase.value}


@router.post('/projects/{project_id}/summary/generate', response_model=SummaryGenerateResponse)
def generate_summary(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)

    decision = db.scalar(
        select(Decision)
        .where(Decision.project_id == project_id, Decision.cycle_number == project.current_cycle)
        .order_by(Decision.id.desc())
    )

    job = AIJob(
        project_id=project_id,
        cycle_number=project.current_cycle,
        actor_type=ActorType.RESEARCHER,
        actor_id=current_user.id,
        job_type=JobType.SUMMARIZE,
        status=JobStatus.PENDING,
        input_payload={'decision': decision.decision.value if decision else 'undecided'},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return SummaryGenerateResponse(job_id=job.id)


@router.post('/projects/{project_id}/export/pdf', response_model=ExportOut)
def export_pdf(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)

    summary = db.scalar(
        select(WorkshopSummary)
        .where(WorkshopSummary.project_id == project_id, WorkshopSummary.cycle_number == project.current_cycle)
        .order_by(WorkshopSummary.id.desc())
    )
    decision = db.scalar(
        select(Decision)
        .where(Decision.project_id == project_id, Decision.cycle_number == project.current_cycle)
        .order_by(Decision.id.desc())
    )

    entries = db.scalars(
        select(PhaseEntry).where(PhaseEntry.project_id == project_id, PhaseEntry.cycle_number == project.current_cycle)
    ).all()
    phase_data = {}
    for e in entries:
        phase_data.setdefault(e.phase.value, [])
        phase_data[e.phase.value].append(f'{e.field_key}: {e.content}')

    phase_text = {k: '\n'.join(v) for k, v in phase_data.items()}
    summary_text = summary.summary_text if summary else 'Summary not generated yet.'
    decision_text = decision.decision.value if decision else 'undecided'

    out_path = f'/app/exports/project_{project_id}_cycle_{project.current_cycle}.pdf'
    file_path = build_pdf(out_path, project.title, phase_text, summary_text, decision_text)

    export = Export(project_id=project_id, cycle_number=project.current_cycle, file_path=file_path)
    db.add(export)
    db.commit()
    db.refresh(export)

    return ExportOut(export_id=export.id, file_path=export.file_path)


@router.get('/projects/{project_id}/export/{export_id}')
def download_export(project_id: int, export_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    project = db.get(Project, project_id)
    ensure_owner(project, current_user)
    export = db.get(Export, export_id)
    if not export or export.project_id != project_id:
        raise HTTPException(status_code=404, detail='Export not found')
    if not Path(export.file_path).exists():
        raise HTTPException(status_code=404, detail='File missing')
    return FileResponse(export.file_path, filename=Path(export.file_path).name)
