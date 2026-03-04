from datetime import datetime
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class ProjectCreate(BaseModel):
    title: str


class ProjectOut(BaseModel):
    id: int
    title: str
    current_phase: str
    current_cycle: int

    class Config:
        from_attributes = True


class InviteOut(BaseModel):
    invite_url: str
    expires_at: datetime


class JoinInviteRequest(BaseModel):
    name: str
    company: str
    consent: bool = Field(default=False)


class JoinInviteResponse(BaseModel):
    participant_id: int
    project_id: int


class PhaseEntryPatch(BaseModel):
    actor_type: str
    actor_id: int
    field_key: str
    content: str


class PhaseEntryPatchResponse(BaseModel):
    entry_version: int
    ai_job_id: int | None = None


class AIJobStatusOut(BaseModel):
    id: int
    status: str
    job_type: str
    fallback_used: bool
    error_message: str | None = None


class AssessmentStartRequest(BaseModel):
    participants: list[int]


class AssessmentScoreRequest(BaseModel):
    actor_type: str
    actor_id: int
    criterion: str
    score: int
    justification: str | None = None


class DecisionRequest(BaseModel):
    decision: str
    justification: str


class SummaryGenerateResponse(BaseModel):
    job_id: int


class ExportOut(BaseModel):
    export_id: int
    file_path: str
