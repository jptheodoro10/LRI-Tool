# LRI Tool Artifact (SBES Functional)

Self-contained artifact for Lean Research Inception (LRI), focused on reproducible local execution.

## Paper Link
Add accepted paper URL here: `TBD`

## Repository Structure
- `backend/`: FastAPI, SQLAlchemy, Alembic, worker logic, tests
- `frontend/`: React app with inline AI suggestions in fields (green)
- `scripts/`: startup and smoke test scripts
- `fixtures/`: deterministic AI fixtures (expandable)
- `docs/`: supporting documentation
- `docker-compose.yml`: local orchestration (`db`, `backend`, `worker`, `frontend`)

## Requirements
- Docker + Docker Compose
- 4 GB RAM recommended
- 2 CPU recommended
- ~2 GB free disk

## Installation
1. Set OPENAI_API_KEY:
   - Set OPENAI_API_KEY on the env file
2. Start stack:
   - `docker compose up --build`
3. Open frontend:
   - `http://localhost:5173`
4. Backend health:
   - `http://localhost:8000/health`

## Default Credentials (seed)
- Email: `researcher@example.com`
- Password: `researcher123`


## Basic Usage Example
1. Login as researcher.
2. Create project.
3. Advance to F2 and create invite URL.
4. Join invite as participant from `/invite/{token}`.
5. Edit fields in F1-F3.
6. Wait for inline suggestion state (`pending -> green suggestion`).
7. Accept/Edit/Dismiss suggestion.
8. In final stage, generate summary and export PDF.

## Smoke Test
With stack running:
- `./scripts/smoke_test.sh`

Expected output contains:
- `Token acquired`
- `Project <id> created`
- `Participant <id> joined`
- `Smoke flow executed`

## Tests
Run backend tests inside container:
- `docker compose exec backend pytest -q`

## Ethical and Legal Notes
- Participant data collected: name and company.
- Consent is mandatory on invite join.
- This artifact does not anonymize exported reports by default.

## Badge Notes
- Functional: fully reproducible local run via Docker Compose.
- Available: create a persistent DOI snapshot (Zenodo/Figshare/OSF) for submission.
