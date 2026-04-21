# LRI Tool – Current System Architecture

## Overview

LRI Tool is a web application that supports Lean Research Inception runs through five phases:

1. Initial canvas definition
2. Alignment and invite generation
3. Problem formulation review
4. Semantic differential assessment
5. Decision and PDF export

The current stack is:

- Frontend: React + Vite
- Backend API: FastAPI
- Persistence: SQLAlchemy + Alembic
- Database: PostgreSQL in Docker, SQLite in tests
- AI provider abstraction: mock mode or OpenAI Responses API

The system follows a layered backend structure:

Router -> Service -> Repository -> Database

## Runtime Topology

The repository ships with four Docker services:

- `db`: PostgreSQL
- `backend`: FastAPI API
- `frontend`: Vite frontend
- `worker`: placeholder process reserved for future background jobs

At the moment, the AI features that matter to the product are request-driven. The worker remains available for future async jobs, but the active AI flows are handled directly by API requests.

## Core Domain

### Run

A run is the main aggregate of the system. It stores the current lifecycle state of one Lean Research Inception execution.

Relevant fields:

- `id`
- `title`
- `owner_user_id`
- `current_phase`
- `current_cycle`
- `status`
- `ai_mode_enabled`
- `problem_synthesis`
- `created_at`
- `updated_at`

Important rules:

- Phase progression is global to the run.
- A pivot creates a new cycle and sends the run back to phase 2.
- `problem_synthesis` is written by the facilitator in phase 5 and reused in the PDF export.

### Participants

Participants belong to a run. The facilitator is also represented as a participant record.

Relevant fields:

- `id`
- `run_id`
- `user_id`
- `email`
- `role`
- `created_at`

Current practical roles:

- `facilitator`: owner/editor of the run
- invited participant/collaborator records created through invite acceptance

### Invites

Invites let external participants join a run through a public tokenized URL.

Relevant fields:

- `id`
- `run_id`
- `public_token`
- `token_hash`
- `role`
- `status`
- `invitee_name`
- `participant_name`
- `accepted_participant_id`
- `expires_at`

Important rules:

- In cycle 1, phase 2 requires at least one generated invite before advancing to phase 3.
- After a pivot, the participant group is kept. The UI prevents generating new invites in follow-up cycles.

## Canvas System

The canvas is reused across phases 1, 2, and 3. The questions are stable and keyed.

Current canonical keys:

- `problem`
- `stakeholders`
- `research_questions`
- `hypotheses`
- `method`
- `evaluation`
- `risks`

### Canvas Questions

`canvas_questions` stores metadata for each field:

- `key`
- `title`
- `prompt_template`

### Canvas Responses

`canvas_responses` stores one response per run, question, and cycle:

- `run_id`
- `question_id`
- `participant_id`
- `cycle`
- `content`
- `updated_at`

Constraint:

- unique `(run_id, question_id, cycle)`

Important implementation detail:

- Only the facilitator can edit canvas responses through the API.
- Participants can view the board in phases 1 to 3, but they do not directly write canvas content.

### Cycle Reuse

When a run pivots:

- the run goes back to phase 2
- `current_cycle` is incremented
- phase 2 is prefilled from the latest previous cycle that has canvas responses
- advancing from phase 2 to phase 3 copies those responses into the new current cycle

## AI Architecture

The AI layer currently contains two user-facing modules and one provider abstraction.

### 1. Phase 1 Recommendations

Purpose:

- help the facilitator fill empty canvas fields using already filled fields as context

Trigger:

- manual action from the phase 1 button

Current frontend behavior:

- the frontend finds empty fields
- it sends one request per empty field in parallel
- each suggestion appears under its canvas as soon as that specific request finishes

Current endpoints:

- `POST /projects/{run_id}/canvas/{question_key}/recommendation`
- `POST /projects/{run_id}/canvas/recommendations` exists and remains compatible for batch generation

Persistence:

- stored in `ai_suggestions`

Stored attributes:

- `status`
- `context_hash`
- `output`
- `error_message`
- timestamps

Key behavior:

- recommendations are available only in phase 1
- recommendations are generated only for empty fields
- `context_hash` prevents unnecessary recomputation for the same context
- stale queued/running suggestions can be marked as `stale`

### 2. Phase 3 Canvas Overview

Purpose:

- help the facilitator analyze each completed phase 3 canvas critically

Trigger:

- manual action from the phase 3 button

Current frontend behavior:

- the canvas must be fully filled
- the frontend sends one request per field in parallel
- each overview appears progressively below its field

Current endpoints:

- `POST /projects/{run_id}/canvas/{question_key}/overview`
- `POST /projects/{run_id}/canvas/overview` for batch generation

Persistence:

- phase 3 overviews are not stored in the database
- they are transient UI state

### 3. LLM Client Abstraction

The backend talks to LLMs through `LLMClient.generate(prompt) -> str`.

Current implementations:

- `MockLLMClient`: deterministic fallback based on a prompt hash
- `OpenAILLMClient`: uses the OpenAI Responses API

Selection rule:

- if `LLM_API_KEY` is configured, OpenAI is used
- otherwise the system falls back to mock mode

This keeps the service layer provider-agnostic.

## Phase Logic

### Phase 1

- facilitator fills the initial board
- AI recommendations can be requested for empty fields
- suggestions are shown inline and can be accepted or dismissed in the UI

### Phase 2

- facilitator manages invite links
- board content remains visible
- advancing to phase 3 requires at least one invite in cycle 1

### Phase 3

- board is reviewed and reformulated
- facilitator remains the only direct editor
- AI overview can be requested only when every field is filled

### Phase 4

- invited participants submit semantic differential scores from 1 to 7
- the facilitator can monitor completion
- participants can optionally add comments per metric

Current required metrics for completion:

- `impact`
- `alignment`
- `feasibility`

Note:

- the domain module still defines `novelty` for compatibility, but the current UI and completion flow use the three metrics above

### Phase 5

- aggregated medians are displayed
- comments are grouped by participant
- facilitator records `GO`, `PIVOT`, or `ABORT`
- a final PDF export is available only after `GO` or `ABORT`

Pivot behavior:

- records a `PIVOT` decision for the current cycle
- resets `problem_synthesis`
- moves the run back to phase 2
- increments `current_cycle`
- keeps the run active

## Score and Result Model

Scores are stored in `scores` with:

- `run_id`
- `participant_id`
- `metric_key`
- `cycle`
- `value`
- `comment`

Constraint:

- unique `(run_id, participant_id, metric_key, cycle)`

Aggregations are computed dynamically in the service layer:

- average
- median
- per-value distribution
- completion counters

## PDF Export

The PDF export uses:

- phase 3 formulated problem content
- phase 4 assessment medians
- phase 5 decision
- facilitator-authored `problem_synthesis`

The export is generated by the backend and stored as an `exports` record with a downloadable file path.

## Backend Layers

### Routers

HTTP boundary and access control.

Main router modules:

- `auth.py`
- `runs.py`
- `canvas.py`
- `invites.py`
- `scores.py`

### Services

Business rules and orchestration.

Current service modules:

- `run_service.py`
- `canvas_service.py`
- `ai_service.py`
- `invite_service.py`
- `score_service.py`
- `pdf_service.py`

### Repositories

Persistence-oriented operations, isolated from business rules.

Current repository modules:

- `run_repository.py`
- `canvas_repository.py`
- `ai_suggestion_repository.py`
- `invite_repository.py`
- `participant_repository.py`
- `score_repository.py`

### Models

SQLAlchemy ORM models for the domain:

- `Run`
- `Participant`
- `Invite`
- `CanvasQuestion`
- `CanvasResponse`
- `AISuggestion`
- `Score`
- `Decision`
- `Export`
- `User`

## Frontend Data Flow

The frontend page for the run phases is centralized in `ProjectPhasePage.jsx`.

Current behavior:

- polls run state every few seconds
- polls assessment completion in phase 4
- autosaves facilitator canvas edits in phases 1 to 3
- renders AI output inline under each field
- uses progressive multi-request flows for:
  - phase 1 recommendations
  - phase 3 overviews

## API Notes

The project exposes both `/runs/...` and `/projects/...` aliases for most main endpoints.

Examples:

- `GET /projects/{id}`
- `GET /projects/{id}/canvas`
- `POST /projects/{id}/advance-phase`
- `POST /projects/{id}/canvas/{field}/recommendation`
- `POST /projects/{id}/canvas/{field}/overview`
- `POST /projects/{id}/scores`
- `POST /projects/{id}/decision`
- `POST /projects/{id}/export/pdf`

## Deployment Notes

### Local

Use Docker Compose:

```bash
docker compose up --build
```

### AI Configuration

Relevant environment variables:

- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `DATABASE_URL`
- `JWT_SECRET`

## Key Design Decisions

1. The run is the source of truth for phase and cycle.
2. Canvas questions are phase-independent and reused.
3. Canvas responses and scores are cycle-scoped.
4. AI recommendations are persisted; phase 3 overviews are transient.
5. The facilitator is the single writer for canvas content.
6. Participants contribute mainly through invites and phase 4 scoring.
7. The LLM provider is abstracted behind a simple synchronous client interface.
8. The worker process is reserved for future asynchronous extensions, but the active AI flows are currently API-driven.
