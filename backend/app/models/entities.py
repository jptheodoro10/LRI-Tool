from datetime import datetime
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Phase(str, Enum):
    F1 = 'F1'
    F2 = 'F2'
    F3 = 'F3'
    F4 = 'F4'
    F5 = 'F5'


class JobType(str, Enum):
    SUGGEST = 'suggest'
    SUMMARIZE = 'summarize'


class JobStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    TIMEOUT = 'timeout'


class DecisionType(str, Enum):
    GO = 'go'
    PIVOT = 'pivot'
    ABORT = 'abort'


class ActorType(str, Enum):
    RESEARCHER = 'researcher'
    PARTICIPANT = 'participant'


class AssessmentCriterion(str, Enum):
    VALUABLE = 'valuable'
    FEASIBLE = 'feasible'
    APPLICABLE = 'applicable'


class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = 'projects'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    current_phase: Mapped[Phase] = mapped_column(SAEnum(Phase), default=Phase.F1)
    current_cycle: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ProjectCycle(Base):
    __tablename__ = 'project_cycles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    close_reason: Mapped[DecisionType | None] = mapped_column(SAEnum(DecisionType), nullable=True)


class Invite(Base):
    __tablename__ = 'invites'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Participant(Base):
    __tablename__ = 'participants'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    invite_id: Mapped[int] = mapped_column(ForeignKey('invites.id'))
    name: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    consent_accepted_at: Mapped[datetime] = mapped_column(DateTime)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PhaseEntry(Base):
    __tablename__ = 'phase_entries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer, default=1)
    phase: Mapped[Phase] = mapped_column(SAEnum(Phase), index=True)
    actor_type: Mapped[ActorType] = mapped_column(SAEnum(ActorType), index=True)
    actor_id: Mapped[int] = mapped_column(Integer, index=True)
    field_key: Mapped[str] = mapped_column(String(120), index=True)
    content: Mapped[str] = mapped_column(Text, default='')
    entry_version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            'project_id', 'cycle_number', 'phase', 'actor_type', 'actor_id', 'field_key', name='uq_phase_entry'
        ),
    )


class AIJob(Base):
    __tablename__ = 'ai_jobs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer)
    actor_type: Mapped[ActorType] = mapped_column(SAEnum(ActorType))
    actor_id: Mapped[int] = mapped_column(Integer)
    job_type: Mapped[JobType] = mapped_column(SAEnum(JobType), index=True)
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus), default=JobStatus.PENDING, index=True)
    input_payload: Mapped[dict] = mapped_column(JSON)
    output_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FieldSuggestion(Base):
    __tablename__ = 'field_suggestions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer)
    phase: Mapped[Phase] = mapped_column(SAEnum(Phase), index=True)
    target_field: Mapped[str] = mapped_column(String(120), index=True)
    source_field: Mapped[str] = mapped_column(String(120))
    suggested_text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_id: Mapped[int] = mapped_column(ForeignKey('ai_jobs.id'), index=True)
    applied_by_user: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AssessmentSession(Base):
    __tablename__ = 'assessment_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default='open')
    frozen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssessmentRespondent(Base):
    __tablename__ = 'assessment_respondents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('assessment_sessions.id'), index=True)
    actor_type: Mapped[ActorType] = mapped_column(SAEnum(ActorType))
    actor_id: Mapped[int] = mapped_column(Integer)


class AssessmentScore(Base):
    __tablename__ = 'assessment_scores'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey('assessment_sessions.id'), index=True)
    actor_type: Mapped[ActorType] = mapped_column(SAEnum(ActorType))
    actor_id: Mapped[int] = mapped_column(Integer)
    criterion: Mapped[AssessmentCriterion] = mapped_column(SAEnum(AssessmentCriterion), index=True)
    score: Mapped[int] = mapped_column(Integer)
    justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint('session_id', 'actor_type', 'actor_id', 'criterion', name='uq_assessment_one'),)


class Decision(Base):
    __tablename__ = 'decisions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer)
    decision: Mapped[DecisionType] = mapped_column(SAEnum(DecisionType))
    justification: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkshopSummary(Base):
    __tablename__ = 'workshop_summaries'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer)
    summary_text: Mapped[str] = mapped_column(Text)
    highlights_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey('ai_jobs.id'), nullable=True)


class Export(Base):
    __tablename__ = 'exports'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey('projects.id'), index=True)
    cycle_number: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
