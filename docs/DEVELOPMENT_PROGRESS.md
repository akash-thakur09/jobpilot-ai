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
- [x] Application state machine with strict state transition validation (`backend/app/workflow/state_machine.py`)
- [x] Append-only application event history with defensive secret scrubbing (`backend/app/workflow/state_machine.py`)
- [x] Browser automation adapter interface (Playwright) (`backend/app/automation/base_adapter.py`, `backend/app/automation/synthetic_adapter.py`, `backend/app/automation/browser_runner.py`)
- [x] Conservative form field mapping and safe input filler (`backend/app/automation/form_mapper.py`, `backend/tests/test_form_mapper.py`)
- [x] Human review & approval queue logic with canonical cryptographic fingerprinting (`backend/app/services/application_workflow_service.py`, `backend/app/workflow/approval_fingerprint.py`)
- [x] Duplicate application prevention & idempotency controls (`backend/app/services/application_workflow_service.py`)
- [x] Mock portal test harness for automated submission verification (`backend/app/automation/mock_portal/server.py`, `backend/tests/test_browser_automation.py`)
- [x] Application workflow API endpoints (`/api/v1/applications`) for preparation, review, cryptographic approval, synthetic execution, event/attempt history, and outcome reconciliation (`backend/app/api/v1/applications.py`, `backend/tests/test_applications_api.py`)

### Phase 6 — Frontend Dashboard
- [x] Vite + React + TypeScript setup in `frontend/` (strict checking, Vitest test runner)
- [x] Tailwind CSS configuration and dark-mode glassmorphic workspace layout
- [x] Typed API client for `/api/v1` with error normalization, network failure detection, and automatic base URL configuration
- [x] Dashboard Overview Screen (`DashboardOverview.tsx`): live discovery counts, eligible counts, pending approval counts, unknown outcome alert, and recent activity
- [x] Jobs Discovery & Matching Screen (`JobsList.tsx`): keyword filtering, remote type filter, deterministic eligibility badges, match scores, evaluation trigger, and application preparation
- [x] Candidate Profile & Master Resume Screen (`CandidateProfileView.tsx`): verified facts, inline skill management, master PDF parser, and draft-to-verified confirmation workflow
- [x] Tailored Resume Workspace (`ResumeWorkspace.tsx`): version cards, SHA-256 checksums, bit-for-bit file integrity verification, factual consistency validator, and direct PDF downloads
- [x] Application Review & Tracking Queue (`ApplicationQueue.tsx`): cryptographic approval with canonical SHA-256 fingerprint, stale approval handling (HTTP 409), synthetic browser run runner, append-only event timeline, attempt history, and guarded outcome reconciliation
- [x] 21 automated frontend tests across API client, formatters, and all workspace screens using Vitest and React Testing Library

### Phase 7 — Scheduled Discovery, Matching Pipeline, and Persistent Notifications
- [x] Persistent in-app notification model with database-backed deduplication, read/dismiss states, and clean Alembic migration (`4b81cf738a92`)
- [x] Configurable background scheduler service (APScheduler with AsyncIOScheduler, process-level concurrency lock, safe startup/shutdown in FastAPI lifespan)
- [x] Dynamic discovery interval reconfiguration (5 to 10080 minutes) and enable/disable controls
- [x] Reusable 12-stage discovery and automated matching pipeline (`DiscoveryMatchingPipeline.execute`) shared by manual triggers and scheduler
- [x] Error isolation across multi-source discovery (`synthetic`, `greenhouse`, `lever`) with status tracking (`COMPLETED`, `PARTIAL_SUCCESS`, `FAILED`)
- [x] Idempotent match notification creation with unique `dedup_key` for newly relevant eligible matches
- [x] Failure notifications for complete and partial run failures with defensive secret scrubbing and sanitized diagnostics
- [x] Scheduler and Notification API endpoints (`/api/v1/scheduler`, `/api/v1/notifications`)
- [x] Frontend Notification Center popover with live unread badge, type icons, mark-read, and dismiss actions
- [x] Frontend Scheduler & Discovery management screen and dashboard overview integration with validated interval updates, manual trigger, latest run stats, and diagnostics inspection modal
- [x] Complete backend test coverage (124 passed tests) and frontend test coverage (27 passed Vitest tests) with verified production build

### Phase 8 — Security and Release Readiness
- [ ] Security audit (path traversal prevention, secret scrubbing, CORS)
- [ ] Retention and deletion procedures
- [ ] Clean installation validation from documented instructions
- [ ] End-to-end integration test execution
- [ ] Release checklist and sign-off
