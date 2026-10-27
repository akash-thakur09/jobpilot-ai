# JobPilot AI

JobPilot AI is a local-first, privacy-focused personal AI job-hunting agent. It continuously discovers relevant job openings across supported job platforms, evaluates them against a verified candidate profile with explainable scoring, generates tailored ATS-friendly resumes grounded strictly in verified facts, and automates permitted application workflows while enforcing human approval before final submission.

---

## Key Features

- **Local-First & Privacy Preserving**: Candidate data, generated resumes, and AI inference run locally on your machine via Ollama (`llama3.1`).
- **Factually Grounded Resumes**: Zero hallucination policy. Resumes only highlight verified skills, achievements, and career history without inventing qualifications.
- **Explainable Match Scoring**: Deterministic rules for mandatory eligibility combined with weighted scoring for skills, experience, and remote/location preferences.
- **Immutable Application History**: Every submitted application preserves the exact resume version, PDF file, and SHA-256 checksum used at submission time.
- **Safe Browser Automation**: Uses Playwright for form filling and resume uploading, strictly enforcing human approval before final submission.
- **Multi-Source Job Discovery**: Adapters for public APIs, company career pages (Greenhouse, Lever), and scheduled discovery.

---

## Quickstart

### Prerequisites
- **Python 3.12+**
- **Node.js 20+** & **npm**
- **Ollama** with `llama3.1:latest` (`ollama run llama3.1`)
- **Docker** (optional, for containerized PostgreSQL) or local PostgreSQL / SQLite for lightweight development

### 1. Clone & Configure
```bash
git clone <repo-url> jobpilot-ai
cd jobpilot-ai
cp .env.example .env
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and the backend API documentation at `http://localhost:8000/docs`.

---

## Core API Endpoints (v1)

### Candidate Profile
- `GET /api/v1/profile` — Retrieve current verified candidate profile
- `POST /api/v1/profile` — Create candidate profile
- `PATCH /api/v1/profile` — Update candidate profile fields
- `POST /api/v1/profile/skills` — Add verified technical or soft skill
- `DELETE /api/v1/profile/skills/{skill_id}` — Delete skill
- `POST /api/v1/profile/experiences` — Add employment history
- `POST /api/v1/profile/educations` — Add education record
- `POST /api/v1/profile/projects` — Add demonstrable project
- `POST /api/v1/profile/import-resume` — Upload & extract master PDF resume into unverified review draft
- `POST /api/v1/profile/import-resume/confirm` — Confirm and save draft as verified profile

### Job Discovery & Management
- `GET /api/v1/jobs` — List jobs with search, company/remote filters, and pagination
- `GET /api/v1/jobs/{job_id}` — Retrieve full job details and requirements
- `GET /api/v1/jobs/sources` — List registered discovery sources and their health
- `POST /api/v1/jobs/discover` — Trigger job discovery for `synthetic`, `greenhouse`, or `lever`

### Job Matching & Scoring
- `POST /api/v1/matching/evaluate/{job_id}` — Evaluate a single job against the candidate profile
- `POST /api/v1/matching/evaluate-all` — Batch-evaluate all discovered jobs
- `GET /api/v1/matching/results` — List match evaluations (with `is_eligible`, `min_score`, pagination)
- `GET /api/v1/matching/results/{job_id}` — Get latest match score and breakdown for a job
- `GET /api/v1/matching/health` — Check matching engine and Ollama AI provider status

### Resume Tailoring & Versioning (Phase 4)
- `POST /api/v1/resumes/generate` — Generate tailored ATS PDF resume for an eligible job (fact validation gate, atomic SHA-256 storage)
- `GET /api/v1/resumes/{version_id}` — Get resume version metadata, validation reports, keyword coverage, and candidate snapshot
- `GET /api/v1/resumes/job/{job_id}` — List all historical generated resume versions for a specific job
- `GET /api/v1/resumes/{version_id}/download` — Stream exact immutable PDF file with cache headers and filename
### Application Workflow & Browser Automation (Phase 5)
- `POST /api/v1/applications/prepare` — Prepare candidate application package, trigger resume generation, calculate canonical approval fingerprint
- `GET /api/v1/applications` — List applications with status and candidate filters
- `GET /api/v1/applications/{id}` — Get single application review package
- `GET /api/v1/applications/{id}/review` — Inspect candidate data snapshot, resume checksum, and approval readiness
- `POST /api/v1/applications/{id}/approve` — Human approval gate with canonical fingerprint validation
- `POST /api/v1/applications/{id}/attempt` — Execute synthetic browser automation runner
- `GET /api/v1/applications/{id}/events` — Application append-only lifecycle event log
- `GET /api/v1/applications/{id}/attempts` — Complete execution attempts history
- `POST /api/v1/applications/{id}/reconcile` — Manual outcome reconciliation

### Scheduled Discovery & Automation Runs (Phase 7)
- `GET /api/v1/scheduler/status` — Get scheduler state, running status, interval, next tick, and latest run telemetry
- `POST /api/v1/scheduler/config` — Update scheduler configuration (enable/disable, discovery interval)
- `POST /api/v1/scheduler/run` — Manually trigger immediate 12-stage discovery and matching pipeline
- `GET /api/v1/scheduler/runs` — List discovery run history with pagination and status filters
- `GET /api/v1/scheduler/runs/{id}` — Inspect specific run and sanitized source diagnostics

### Persistent In-App Notifications (Phase 7)
- `GET /api/v1/notifications` — List notifications with read/dismissed state filtering and pagination
- `GET /api/v1/notifications/unread-count` — Get count of active unread notifications
- `POST /api/v1/notifications/{id}/read` — Mark notification as read
- `POST /api/v1/notifications/read-all` — Mark all unread notifications as read
- `POST /api/v1/notifications/{id}/dismiss` — Dismiss notification from active view

---

## Scheduler Architecture, Recovery & Operational Guarantees

1. **Unified Pipeline**: Manual and scheduled discovery execute the exact same 12-stage pipeline (`DiscoveryMatchingPipeline.execute`) with rate limiting, error isolation, deterministic eligibility, scoring, and persistent notification generation.
2. **Process Concurrency Lock**: In-memory `asyncio.Lock` prevents overlapping discovery runs within a single instance.
3. **Single-Scheduler Deployment**: Supported deployments run a single scheduler instance. The concurrency lock coordinates work strictly within a single Python process; multi-worker processes (e.g. `gunicorn -w 4` or multiple `uvicorn` instances) without external distributed locks must run with `SCHEDULER_ENABLED=false` on all but one designated worker.
4. **Crash and Restart Recovery**: If the application process terminates abruptly while a discovery run is executing, `SchedulerService.start()` automatically detects orphaned `RUNNING` discovery records on restart and transitions them to `FAILED` with sanitized error summaries (`"Interrupted by process termination or restart"`).
5. **Missed Run Coalescence**: If the system is offline during scheduled ticks, missed intervals coalesce safely without queue bombardment. The next tick triggers at `now() + interval_minutes`.
6. **Non-Negotiable Safety**: Scheduled runs perform job fetching and matching **ONLY**. Applications are **never** prepared, approved, or submitted by background tasks. `JOBPILOT_REAL_SUBMISSION_ENABLED=false` remains enforced by default.

---

## Supported Job Discovery Sources

- `synthetic`: Local mock adapter providing verified test listings (Remote Python, Senior Backend, Fullstack, Disqualified Frontend) for automated end-to-end testing without external network dependencies.
- `greenhouse`: Real public Greenhouse job boards (e.g. `https://boards-api.greenhouse.io/v1/boards/{token}/jobs`).
- `lever`: Real public Lever job boards (e.g. `https://api.lever.co/v0/postings/{token}`).

---

## Inspecting Runs and Diagnostics

- Run history and telemetry can be inspected via `GET /api/v1/scheduler/runs` and `GET /api/v1/scheduler/runs/{run_id}` or directly in the frontend Scheduler Dashboard.
- When a discovery run encounters partial or total failure, errors are sanitized to redact credentials, tokens, or system traces before persistence.
- Notifications of type `RUN_FAILED` or `RUN_WARNING` are automatically generated and linked to the run record for immediate triage.

---

## Database Migrations

JobPilot AI uses Alembic for declarative schema migrations:

```bash
# Check current revision status:
alembic current

# Run migrations to head:
alembic upgrade head

# Downgrade one revision (if needed):
alembic downgrade -1
```

Current head revision: `4b81cf738a92` (adds persistent notifications table with deduplication keys and cascade-null references to jobs and automation runs).

---

## Verified Local Startup Commands

### Start Backend
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
# Recommended local development runner (binds strictly to loopback 127.0.0.1):
python run.py
```

### Start Frontend
```powershell
cd frontend
npm run dev
```

### Run Full Test Suites
```powershell
# Backend Suite (130 tests):
cd backend
.\.venv\Scripts\pytest.exe -v

# Resume Integrity Acceptance Suite (7 tests):
.\.venv\Scripts\pytest.exe tests\acceptance\test_resume_version_integrity.py -v

# Frontend Suite (27 Vitest tests) & Production Build:
cd frontend
npx vitest run
npm run build
```

---

## Documentation
- [Project Specification](docs/PROJECT_SPEC.md)
- [Development Progress Checklist](docs/DEVELOPMENT_PROGRESS.md)

---

## License
MIT License.
