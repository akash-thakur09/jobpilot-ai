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
- [ ] Backend package directory structure (`backend/app/...`)
- [ ] Dependency specification (`backend/pyproject.toml` or `requirements.txt`)
- [ ] Application configuration (`backend/app/core/config.py`)
- [ ] Structured logging and error handling
- [ ] Async Database engine & session management (`backend/app/db/session.py`)
- [ ] Core SQLAlchemy declarative models (Candidate, Job, Match, Resume, Application)
- [ ] Alembic setup and initial migration
- [ ] FastAPI application factory with versioned `/api/v1` routers
- [ ] Health and readiness endpoints (`/health`, `/api/v1/health`)
- [ ] Pytest harness and baseline test suite
- [ ] Docker Compose definition (`docker-compose.yml`)
- [ ] Backend verification test execution

### Phase 2 — Candidate Profile and Job Discovery
- [ ] Candidate profile CRUD and validation schemas
- [ ] Master resume extraction and confirmation logic
- [ ] Job source adapter interface (`BaseJobSourceAdapter`)
- [ ] Synthetic / Greenhouse / Lever job collectors
- [ ] Job normalization, persistence, and deduplication logic
- [ ] Scheduled discovery runner with concurrency controls
- [ ] Unit and integration tests for discovery & deduplication

### Phase 3 — Matching Engine
- [ ] Deterministic eligibility filter rules (mandatory skills, location, work auth)
- [ ] Configurable weighted scoring engine (skills, title, experience, salary)
- [ ] Semantic matching adapter interface (with Ollama `llama3.1` integration)
- [ ] Explainable match breakdown generator
- [ ] Unit tests for positive matches, borderline matches, and disqualified listings

### Phase 4 — Resume Generation and Versioning
- [ ] Structured resume schema (truthful tailoring without hallucination)
- [ ] Factual consistency validator (rejects claims not in candidate profile)
- [ ] ATS-friendly PDF generator (clean typography, parseable text)
- [ ] PDF text extraction validator (ensures text is selectable and accurately rendered)
- [ ] SHA-256 checksum computation and atomic disk persistence
- [ ] Immutable ResumeVersion database records
- [ ] Unit tests proving profile updates do not alter historical resume records

### Phase 5 — Application Workflow
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
