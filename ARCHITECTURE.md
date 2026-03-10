# LRI Tool – System Architecture

## Overview

The LRI Tool is a web application that supports the execution of the Lean Research Inception (LRI) framework.

The system allows a facilitator (recruiter/researcher) to create a **Run** of the framework and guide participants through different phases. Participants collaborate by filling canvases, receiving AI assistance, and submitting evaluations.

The system must support:

- Collaborative runs with multiple participants
- Canvas-based structured inputs
- Automatic AI suggestions for unfilled canvases
- Invite links for external collaborators
- Score submission and aggregation
- Phase progression across the framework

The architecture follows a layered backend structure: Router → Service (business logic) → Repository (DB access) → Database

---

# Core Domain Concepts

## Run

A **Run** represents one execution of the Lean Research Inception framework.

All participants collaborate inside the same run.

Properties:

- `id`
- `current_phase`
- `ai_mode_enabled`
- `status`
- `created_at`
- `updated_at`

Important rule:

> Phase progression is global to the run.  
> Participants never have their own phase state.

---

## Participants

Participants represent users collaborating inside a run.

Roles may include:

- facilitator / recruiter
- invited collaborator
- reviewer

Properties:

- `id`
- `run_id`
- `user_id OR email`
- `role`
- `created_at`

---

## Invites

Invite links allow external collaborators to join a run.

Properties:

- `id`
- `run_id`
- `token_hash`
- `role`
- `status`
- `expires_at`
- `accepted_participant_id`

Invite flow:

1. Facilitator generates invite
2. Invite link is shared
3. Guest opens link and accepts invite
4. Participant record is created

---

# Canvas System

Canvases represent structured questions that participants must answer.

Important rule:

> Canvases are **not tied to phases in the database**.

Different phases may reuse the same canvas structure.

Example:

- Phase 1 canvases
- Phase 3 canvases (same structure, but collaborative)

Canvases are identified using a **stable key**.

---

## Canvas Questions

The system contains predefined canvas questions.

These are inserted via **seed data**.

Properties:

- `id`
- `key` (unique identifier)
- `title`
- `prompt_template`

Example keys:
problem
stakeholders
research_questions
hypotheses
method
evaluation
risks

---

## Canvas Responses

Participants submit answers to canvases.

Only **one final response per run per canvas** exists.

Properties:

- `id`
- `run_id`
- `question_id`
- `participant_id`
- `content`
- `updated_at`

Constraint: UNIQUE (run_id, question_id)

Meaning:

Each canvas has a single current answer for the run.

---

# AI Assistance

AI assistance helps generate suggestions for canvases that have not yet been answered.

AI suggestions are automatically triggered when a participant submits a canvas response.

There is **no manual "generate AI" button**.

---

## AI Trigger Logic

When a participant submits a canvas response:

1. The response is saved
2. If `ai_mode_enabled == true`:
3. The system gathers all current responses
4. The responses become the **context**
5. AI suggestions are generated for all canvases that:

- do not yet have responses

---

## AI Suggestions

Suggestions are stored in the database.

Properties:

- `id`
- `run_id`
- `question_id`
- `status`
- `context_hash`
- `output`
- `error_message`
- `created_at`
- `updated_at`

Constraint: UNIQUE (run_id, question_id)

`context_hash` ensures suggestions are not recomputed if the context has not changed.

---

# Phase Logic

The framework progresses through phases.

Example phases:

1 — Initial canvas completion  
2 — Alignment / discussion  
3 — Collaborative canvas refinement  
4 — Participant scoring  
5 — Results and averages / Deicison Go/Pivot/Abort

The current phase is stored in the **Run** object. run.current_phase

---

# Phase 1 – Canvas + AI Assistance

Researcher fill canvases.

AI suggestions are generated automatically using existing responses.

Suggestions help fill missing canvases.

---

# Phase 2 - Canvas alignment

Researcher invites participantes by generating invite links.
Participants discuss and align on canvas responses.
Participantes cannot edit the canvases.

# Phase 3 – Collaborative Canvas

Phase 3 reuses the **same canvas system as Phase 1**, but includes invited collaborators.

Differences from Phase 1:

- participants include invited guests
- multiple people may contribute to the discussion

Database structure remains the same.

---

# Phase 4 – Score Submission

Participants submit numeric scores evaluating aspects of the project.
These scores must be persisted in the database.
Participants can also give comments on each aspect, that will be displayed in Phase 5.

---

## Scores

Properties:

- `id`
- `run_id`
- `participant_id`
- `metric_key`
- `value`
- `created_at`

Constraint: UNIQUE (run_id, participant_id, metric_key)

Example metrics:
feasibility
impact
novelty
alignment

---

# Phase 5 – Score Aggregation

Phase 5 displays aggregated results.

The system computes median across all submitted scores.

These median are displayed in the UI.

Aggregations may be computed:

- dynamically in queries
- or cached in a results table if necessary.

---

The researcher can choose to 'Go', 'Pivot' or 'Abort'.

- If he chooses 'Pivot', the global state of phase goes back to phase 2. Both researcher and participants go back to phase 2. The porpuse of the 'Pivot' decision is to reformulate the problem, therefore the project is not over and will restart from phase 2. The researcher can no longer invite more participants. The phase 2 canvases contain the answers submitted before. The will, then, formulated the problem again in phase 3 and in phase 4 the participants will again evaluate. On phase 5 the reseracher will make another decision.

# Backend Structure

Backend layers:
app/
routers/
runs.py
canvas.py
invites.py
scores.py

services/
run_service.py
canvas_service.py
ai_service.py
score_service.py

repositories/
run_repository.py
canvas_repository.py
invite_repository.py
score_repository.py

models/
run.py
participant.py
invite.py
canvas_question.py
canvas_response.py
ai_suggestion.py
score.py

---

# AI Integration

AI generation is handled through an abstraction layer.
LLMClient.generate(prompt) -> str

The implementation may use:

- Gemini
- OpenAI
- other providers

The rest of the system must remain provider-agnostic.

---

# Background Jobs

AI suggestions are processed asynchronously.

Initial implementation:

- FastAPI BackgroundTasks

Future production option:

- Redis Queue (RQ)
- Celery

---

# Frontend Data Flow

The frontend retrieves updates via polling.

Endpoints:
GET /runs/{id}
GET /runs/{id}/canvas
GET /runs/{id}/scores

Polling interval:

2–5 seconds.

This allows participants to see updates from other collaborators.

---

# Key Design Principles

1. **Run is the source of truth**
2. **Phases are global**
3. **Canvases are identified by keys**
4. **AI suggestions on Phase 1 are obtained when the researcher clicks the 'Get Ai suggestion' button**
5. **Responses are persisted**
6. **Scores are persisted**
7. **Backend logic lives in services**
8. **Database constraints enforce consistency**

---

# Deploy

The same codebase supports two deployment modes:

## 1) Web deployment (test/production)

- Frontend deployed as a static web app (for example Vercel or Netlify)
- Backend API deployed as a FastAPI service (for example Render, Railway, Fly.io, or similar)
- Worker deployed as a separate service (same backend image, worker command)
- PostgreSQL deployed as a managed database service
- AI runs with provider credentials configured in environment variables

Recommended backend/worker environment variables:

- `AI_MODE=on`
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_TIMEOUT_SECONDS`
- `DATABASE_URL`
- `JWT_SECRET`

In this mode, the deployed frontend calls the deployed backend API, and the backend/worker call the configured LLM provider API.

## 2) Open-source local deployment (Docker)

- Repository remains open source for anyone to clone
- Local execution remains available with Docker Compose
- Current `docker-compose.yml` runs all required services:
  - `db`
  - `backend`
  - `worker`
  - `frontend`

Local usage:

1. Clone repository
2. Copy `.env.example` to `.env`
3. Run `docker compose up --build`

This provides a reproducible local stack while preserving a separate web-deployed version.
