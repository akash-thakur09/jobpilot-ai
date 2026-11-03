# JobPilot AI

JobPilot AI is a local-first, privacy-focused personal AI job-hunting agent. It continuously discovers relevant job openings across supported job platforms, evaluates them against a verified candidate profile with explainable scoring, generates tailored ATS-friendly resumes grounded strictly in verified facts, and automates permitted application workflows while enforcing human approval before final submission.

---

## Key Features

- **Local-First & Privacy Preserving**: Candidate data, generated resumes, and AI inference run locally on your machine via Ollama (`llama3.1`).
- **Factually Grounded Resumes**: Zero hallucination policy. Resumes only highlight verified skills, achievements, and career history without inventing qualifications.
- **Explainable Match Scoring**: Deterministic rules for mandatory eligibility combined with weighted scoring for skills, experience, and remote/location preferences (Scoring Policy Version 1.1.0).
- **Conservative Duplicate Detection**: Multi-signal cross-source duplicate clustering with location preservation and manual review controls.
- **Authoritative Freshness Tracking**: Source-authoritative status tracking (Active, Potentially Stale, Confirmed Closed, Unknown) with live probe verification.
- **Candidate Feedback Loop**: Deterministic score adjustments from user feedback (Relevant, Not Relevant, Already Applied, Not Interested, Duplicate).
- **Immutable Application History**: Every submitted application preserves the exact resume version, PDF file, and SHA-256 checksum used at submission time.
- **Safe Browser Automation**: Uses Playwright for form filling and resume uploading, strictly enforcing human approval and blocking real submissions by default.
- **Multi-Source & Indian Job Board Integrations**: Built-in support for ATS platforms (Greenhouse, Lever), regional Indian job boards (Naukri.com, Instahyre, Cutshort, Hirist, Foundit), and aggregators (LinkedIn India, Indeed India) with zero-circumvention compliance, CTC/LPA normalization, and alert/manual ingestion engines.

---

## User Guide & Documentation Suite

A complete, exhaustive documentation suite is available in [`docs/user-guide/`](docs/user-guide/):

1. **[Application Overview](docs/user-guide/APPLICATION_OVERVIEW.md)**: High-level overview, core problem statement, daily day-in-the-life walkthrough, and comparisons to manual job searching.
2. **[Complete Feature Inventory](docs/user-guide/FEATURES_AND_FUNCTIONALITY.md)**: Detailed reference covering all 34 feature areas across discovery, matching, resume tailoring, and tracking.
3. **[Complete User Manual & End-to-End Workflow](docs/user-guide/USER_MANUAL.md)**: 19-stage pipeline deep dive with Mermaid diagrams, walkthrough of a real job from discovery to offer, and a screen-by-screen, click-by-click manual for every UI view and modal.
4. **[Technical Architecture & Pipeline Internals](docs/user-guide/TECHNICAL_ARCHITECTURE.md)**: Database ER diagrams, application lifecycle state machine, scoring formulas (Policy 1.1.0), SHA-256 approval fingerprinting, and security boundaries.
5. **[Setup, Configuration & Daily Operations Guide](docs/user-guide/SETUP_AND_DAILY_USAGE.md)**: Installation, database migrations, environment variables, source configuration, and the 15-minute daily job-search routine.
6. **[Troubleshooting & Diagnostic Guide](docs/user-guide/TROUBLESHOOTING.md)**: Diagnostic matrix covering 19 common failure modes, error messages, root causes, and exact remediation commands.
7. **[System Limitations & Future Roadmap](docs/user-guide/LIMITATIONS_AND_ROADMAP.md)**: Clear classification of current boundaries, user prerequisites, external dependencies, and planned enhancements.
8. **[Daily Job-Search Checklist](docs/user-guide/DAILY_JOB_SEARCH_CHECKLIST.md)**: Actionable checklists for initial setup, daily morning triage (10–15 mins), and weekly pipeline reviews.

---

## Indian Job Board Integrations & Ingestion Modes

JobPilot AI integrates with seven major Indian hiring platforms while strictly adhering to ethical, legal, and anti-bot boundaries:

| Platform | Source Type | Integration Status | Supported Ingestion Modes | Salary / CTC Support |
| :--- | :--- | :--- | :--- | :--- |
| **Naukri.com** | `job_board` | `MANUAL_IMPORT_ONLY` | Inbound Email Alerts, Structured JSON | LPA (Lakhs INR), 0–200 LPA range |
| **Instahyre** | `job_board` | `MANUAL_IMPORT_ONLY` | Opportunity Digest, Structured Export | LPA + Equity / ESOP metadata |
| **Cutshort** | `job_board` | `MANUAL_IMPORT_ONLY` | Fast-Track Alerts, Structured JSON | LPA + Skills tags |
| **Hirist** | `job_board` | `CONFIGURATION_REQUIRED` | Configured HTTPS RSS Feeds, Alert Ingestion | LPA + Tech categorization |
| **Foundit (Monster)** | `job_board` | `MANUAL_IMPORT_ONLY` | Inbound Job Alerts, Manual JSON | LPA range + Experience bracket |
| **LinkedIn India** | `aggregator` | `AUTHORIZATION_REQUIRED` | Saved Alert Ingestion, Partner API (when authorized) | Disclosed INR/USD ranges |
| **Indeed India** | `aggregator` | `MANUAL_IMPORT_ONLY` | Inbound Job Alerts, Structured JSON Import | Converted annual INR to LPA |
| **Greenhouse** | `ats` | `AVAILABLE` | Public Employer Boards | Board Token Ingestion |
| **Lever** | `ats` | `AVAILABLE` | Public Employer Boards | Site Token Ingestion |

For full architectural analysis and technical specifications, see [`docs/INDIAN_JOB_SOURCES_INTEGRATION_SPEC.md`](docs/INDIAN_JOB_SOURCES_INTEGRATION_SPEC.md).

---

## Quickstart

### Prerequisites
- **Python 3.12+**
- **Node.js 20+** & **npm**
- **Ollama** with `llama3.1:latest` (`ollama run llama3.1`)
- **Docker** (optional, for containerized PostgreSQL) or local SQLite for lightweight local development

### 1. Clone & Configure
```bash
git clone <repo-url> jobpilot-ai
cd jobpilot-ai
cp .env.example .env
```

### 2. Backend Setup
```powershell
cd backend
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python run.py
```

### 3. Frontend Setup
```powershell
cd ../frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and the backend API documentation at `http://localhost:8000/docs`.

---

## Environment Variables & Safe Defaults

The application strictly validates configuration upon startup (`validate_startup_configuration`).

| Variable | Default | Purpose / Safety Rule |
| :--- | :--- | :--- |
| `APP_HOST` | `127.0.0.1` | Local loopback binding. Non-localhost bindings log security warnings. |
| `APP_PORT` | `8000` | Backend API server port. |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | Allowed frontend origins. |
| `JOBPILOT_REAL_SUBMISSION_ENABLED` | `False` | **CRITICAL SAFETY BOUNDARY**. Real external submissions are disabled by default. Automatically enforced to `False` on local start. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./jobpilot.db` | Async SQLAlchemy database URI. |
| `RESUME_STORAGE_DIR` | `./storage/resumes` | Directory for immutable resume PDFs with atomic SHA-256 naming. |
| `SCREENSHOT_STORAGE_DIR` | `./storage/screenshots` | Directory for submission audit screenshots. |
| `SCHEDULER_ENABLED` | `True` | Background discovery scheduler enable flag. |
| `EMAIL_ENABLED` | `False` | SMTP notification delivery enable flag. Falls back to mock logger when False. |
| `SMTP_HOST` | `""` | Outbound SMTP server hostname. |
| `SMTP_PORT` | `587` | SMTP port (587 STARTTLS / 465 SSL). |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama inference URL. |
| `OLLAMA_MODEL` | `llama3.1:latest` | Local LLM model tag. |

---

## Supported Source Configuration & Rate Limits

JobPilot AI supports public, read-only career board APIs. It never submits applications or crawls arbitrary websites during discovery.

### Supported Adapters
1. **Synthetic (`synthetic`)**:
   - Built-in offline testing fixture emitting diverse job listings (remote Python, senior backend, disqualified, etc.) without network access.
   - Config JSON: `{"count": 5, "company_name": "AcmeCorp"}`.
2. **Greenhouse (`greenhouse`)**:
   - Public board API: `https://boards-api.greenhouse.io/v1/boards/{token}/jobs`.
   - Site/Board Token: Specify the company board token (e.g. `{"token": "stripe"}`).
   - Rate Limits: 30 requests/min default with HTTP 429 detection and `Retry-After` header backoff.
   - Pagination: `limit` parameter supported.
   - Single-Job Probe: Checks `https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}` for active vs 404/closed status.
3. **Lever (`lever`)**:
   - Public postings API: `https://api.lever.co/v0/postings/{token}`.
   - Site/Board Token: Specify the company board token (e.g. `{"token": "netflix"}`).
   - Rate Limits: 30 requests/min default with HTTP 429 detection and backoff.
   - Pagination: Native `limit` parameter supported.
   - Single-Job Probe: Probes `https://api.lever.co/v0/postings/{token}/{job_id}`.

### Source Failure Isolation
- Discovery runs execute with source-level error isolation (`DiscoveryMatchingPipeline`).
- If one source fails (HTTP 429 rate limit, 500 server error, network timeout), other sources proceed normally.
- Runs record status: `COMPLETED` (all succeeded), `PARTIAL_SUCCESS` (some succeeded), or `FAILED` (all failed).
- Diagnostics are sanitized to prevent credential or internal trace leakage.
- Source outages or network timeouts **never** mark existing listings as closed.

---

## Live Status & Freshness Verification

- **Automatic Staleness**: Jobs unseen for > 30 days without authoritative re-discovery transition to `POTENTIALLY_STALE`.
- **Authoritative Closure**: Only authoritative closure signals (e.g. HTTP 404 from single-job API probe) transition jobs to `CONFIRMED_CLOSED`.
- **Live Probe Verification**:
  - API endpoint: `POST /api/v1/jobs/{job_id}/freshness/verify`.
  - Frontend: "Verify Live Status" button in `JobDetailModal`.
  - If a source adapter is unreachable or encounters network failure during a probe, status is recorded as `UNKNOWN` rather than claiming success.

---

## Cross-Source Duplicate Detection & Feedback

- **Staged Duplicate Detection**:
  1. Exact canonical URL matching.
  2. Employer token and normalized job title blocking.
  3. Multi-signal similarity scoring (company token overlap, title fuzzy match, remote compatibility, description Jaccard overlap).
- **Physical Location Protection**: Separate physical vacancies in different cities apply a -0.35 deduction, preventing false merges.
- **Non-Destructive Clustering**: Both source records, original URLs, and application histories are preserved in `JobDuplicateCluster`.
- **Review Workflow**: Users can review duplicates via `GET /api/v1/jobs/duplicates` and `POST /api/v1/jobs/duplicates/{id}/review` (CONFIRM or DISMISS).
- **User Feedback**:
  - Feedback types: `RELEVANT`, `NOT_RELEVANT`, `ALREADY_APPLIED`, `NOT_INTERESTED`, `DUPLICATE_LISTING`.
  - Applied exactly once per match evaluation.
  - **Deterministic Rule**: Hard eligibility disqualification (e.g. mandatory citizenship) **always** wins and cannot be overridden by user feedback.

---

## Scheduler Architecture, Recovery & Multi-Process Limits

1. **Single-Scheduler Process Model**:
   - APScheduler runs as an in-process `AsyncIOScheduler` within the FastAPI lifespan.
   - Discovery concurrency is governed by an in-memory `asyncio.Lock` preventing overlapping runs.
   - **Multi-Process Limitation**: Running multiple worker processes (e.g. `gunicorn -w 4` or multiple `uvicorn` instances) without external distributed locks is not supported with the scheduler enabled. Run with a single process or set `SCHEDULER_ENABLED=false` on all worker processes except one designated scheduler worker.
2. **Crash & Restart Recovery**:
   - If the application process terminates abruptly during discovery, `SchedulerService.start()` detects orphaned `RUNNING` discovery runs upon restart and transitions them to `FAILED` with sanitized error summaries (`"Interrupted by process termination or restart"`).
3. **Missed Run Coalescence**:
   - If the system is offline during scheduled ticks, missed intervals coalesce safely without queue bombardment. The next tick triggers at `now() + interval_minutes`.

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

- **Current Alembic Head**: `e145f6789abc`
  - Revises: `d934b51c8a2f`
  - Adds database indexes on `jobs.canonical_url` and `jobs.discovered_at` for high-performance deduplication and filtering.

---

## Offline Ranking Evaluation

JobPilot AI includes an offline recommendation and ranking benchmark framework:

```powershell
backend\.venv\Scripts\python.exe backend/evaluation/run_ranking_eval.py
```

### Metrics & Benchmark Performance
- **Dataset**: 12 diverse synthetic fixtures across strong matches, weak matches, disqualified postings, stale listings, and duplicate pairs.
- **Precision@3**: `1.0000`
- **Precision@5**: `0.8000`
- **NDCG@3**: `1.0000`
- **NDCG@5**: `0.9178`
- **Duplicate Detection F1**: `1.0000` (Precision: 1.0, Recall: 1.0)
- **Freshness Classification Accuracy**: `1.0000`
- Output: Persisted to `storage/evaluation_results.json`.

*Limitation Note*: Offline ranking evaluation uses static benchmark fixtures. Production ranking should be evaluated against real user interaction volumes over time.

---

## Operational Security & Safe Local Deployment

1. **Localhost Binding Default**: The backend binds strictly to `127.0.0.1` by default.
2. **Public Exposure Warning**: JobPilot AI is designed for local-first single-user personal use. Exposing the backend or frontend to public networks requires an appropriate authentication layer, TLS reverse proxy, and network firewalls.
3. **Secret Protection**: API tokens, database credentials, and email credentials remain in local `.env` and are never committed or exposed to frontend bundles.
4. **Sanitized Diagnostics**: Application error responses redact system stack traces and candidate sensitive details.
5. **Resume Integrity**: Uploaded resumes and tailored PDF artifacts are validated for file size, MIME type, and bit-for-bit SHA-256 integrity before use.
6. **Immutable Historical Records**: Applications and generated resume versions cannot be mutated once created.

---

## Verified Test Suites

### Backend Tests (175 passed tests across 25 modules)
```powershell
cd backend
.\.venv\Scripts\pytest.exe -v
```

### Acceptance & Regression Suites
```powershell
# Phase 12 Live Adapters, Data Quality, and E2E Flow:
.\.venv\Scripts\pytest.exe tests\test_live_sources_and_adapters.py tests\test_data_quality_and_ranking_regressions.py tests\test_production_readiness_e2e.py -v

# Resume Integrity Acceptance Suite:
.\.venv\Scripts\pytest.exe tests\acceptance\test_resume_version_integrity.py -v
```

### Frontend Tests (41 passed Vitest tests) & Build
```powershell
cd frontend
npm run test
npm run build
```

---

## License
MIT License.
