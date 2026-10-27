# JobPilot AI — Development Progress Checklist

## Legend
- [x] Completed and verified
- [/] In progress
- [ ] Not started

---

### Phase 0 — Workspace Audit and Specification
- [x] Workspace inspection (tools, runtimes, environment)
- [x] Repository initialization (`git init`)
- [x] Minimal foundational configuration (`.gitignore`, `.env.example`)
- [x] Living project specification (`docs/PROJECT_SPEC.md`)
- [x] Development progress tracker (`docs/DEVELOPMENT_PROGRESS.md`)
- [x] Project README (`README.md`)
- [x] Storage directories setup with `.gitkeep` (`storage/resumes`, `storage/screenshots`)

### Phase 1 — Environment and Backend Foundation
- [x] Backend package directory structure (`backend/app/...`)
- [x] Dependency specification (`backend/requirements.txt`)
- [x] Application configuration (`backend/app/core/config.py`)
- [x] Structured logging and error handling (`backend/app/core/logging.py`)
- [x] Async Database engine & session management (`backend/app/db/session.py`)
- [x] Core SQLAlchemy declarative models (`CandidateProfile`, `Job`, `MatchScore`, `ResumeVersion`, `Application`, etc.)
- [x] Alembic setup and initial migration (`2051ba9838c8_initial_schema.py`)
- [x] FastAPI application factory with versioned `/api/v1` routers (`backend/app/main.py`)
- [x] Health and readiness endpoints (`/health`, `/api/v1/health`, `/api/v1/health/ready`)
- [x] Pytest harness and baseline test suite (`backend/tests/test_health.py`, `test_models.py`)
- [x] Docker Compose definition (`docker-compose.yml`)
- [x] Backend verification test execution (4 passing unit & integration tests)

### Phase 2 — Candidate Profile and Job Discovery
- [x] Candidate profile CRUD and validation schemas (`backend/app/schemas/candidate.py`, `backend/app/api/v1/profile.py`)
- [x] Master resume extraction and confirmation logic (`backend/app/services/resume_parser.py`, handling encrypted/empty/corrupt files)
- [x] Job source adapter interface (`backend/app/collectors/base.py`)
- [x] Synthetic, Greenhouse, and Lever job collectors (`backend/app/collectors/synthetic.py`, `greenhouse.py`, `lever.py`)
- [x] Job normalization, persistence, and deduplication logic (`backend/app/services/job_discovery_service.py`)
- [x] AutomationRun tracking for discovery operations
- [x] Unit and integration tests (20 passing tests across candidate profile, resume import, discovery, deduplication, and adapter fixtures)

### Phase 3 — Matching Engine
- [x] Deterministic eligibility filter rules (`backend/app/matching/eligibility.py`: work auth, location/remote, experience, mandatory skills)
- [x] Configurable weighted scoring engine (`backend/app/matching/scoring.py`: 40% skills, 20% title, 15% experience, 10% projects, 10% location/remote, 5% salary)
- [x] Skill alias normalization & distinct technology separation (`backend/app/matching/skill_registry.py`)
- [x] Semantic matching adapter interface with local Ollama provider (`backend/app/providers/ollama.py` with prompt injection defense)
- [x] Explainable match breakdown generator & persistence (`backend/app/services/matching_service.py`, `backend/app/api/v1/matching.py`)
- [x] Schema migration for audit fields (`667e479abab5_add_matching_engine_fields_to_match_.py`)
- [x] Unit and integration tests (33 passing tests covering positive matches, borderline matches, disqualified constraints, prompt injection resilience, and Ollama offline fallback)

### Phase 4 — Resume Generation and Versioning
- [x] Structured resume schema (truthful tailoring without hallucination) (`backend/app/resumes/schemas.py`)
- [x] Factual consistency validator (rejects claims not in candidate profile) (`backend/app/resumes/fact_validator.py`)
- [x] ATS-friendly PDF generator (single-column, clean typography, parseable text) (`backend/app/resumes/pdf_renderer.py`)
- [x] PDF text extraction validator (pypdf text extraction and section verification) (`backend/app/resumes/pdf_verifier.py`)
- [x] SHA-256 checksum computation and atomic disk persistence (`backend/app/resumes/storage_service.py`)
- [x] Immutable ResumeVersion database records (`backend/app/models/matching.py`, `backend/app/services/resume_version_service.py`)
- [x] Unit tests proving profile updates do not alter historical resume records (`backend/tests/test_resume_tailoring.py`)
- [x] Resume generation, download, and file integrity verification API endpoints (`backend/app/api/v1/resumes.py`)
- [x] Clean Alembic migration: `2692bda4ba04_add_resume_versioning_validation_fields.py`

### Phase 5 — Application Workflow
- [x] Application & SubmissionAttempt data models with uniqueness constraint on `(candidate_id, job_id)`, approval gate fields, and clean Alembic migration (`3f63fd0f4fae`)
- [ ] Application state machine with strict state transition validation
- [ ] Append-only application event history
- [ ] Browser automation adapter interface (Playwright)
- [ ] Form field mapping and safe input filler
- [ ] Human review & approval queue logic
- [ ] Duplicate application prevention & idempotency controls
- [ ] Mock portal test harness for automated submission verification

### Phase 6 — Frontend Dashboard
- [ ] Vite + React + TypeScript setup in `frontend/`
- [ ] Tailwind CSS configuration and design system
- [ ] Typed API client for `/api/v1`
- [ ] Overview dashboard (discovery metrics, pending actions, status breakdown)
- [ ] Jobs view (filtering, search, match score display, detail modal)
- [ ] Resume preview and download viewer
- [ ] Application workflow queue (review, approve, history timeline)
- [ ] Candidate profile & preferences editor
- [ ] Source health and scheduler monitor

### Phase 7 — Notifications and Reliability
- [ ] Local in-app notification store and API
- [ ] Optional external notification dispatcher (Telegram / Email)
- [ ] Failure recovery & retry with backoff for network operations
- [ ] Diagnostic logging and health metrics
- [ ] Verification under interrupted runs and restart scenarios

### Phase 8 — Security and Release Readiness
- [ ] Security audit (path traversal prevention, secret scrubbing, CORS)
- [ ] Retention and deletion procedures
- [ ] Clean installation validation from documented instructions
- [ ] End-to-end integration test execution
- [ ] Release checklist and sign-off
