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

### Phase 8 — End-to-End Validation and Reliability Hardening
- [x] Baseline audit of services, scheduler lifecycle, database migration state, acceptance suites, and frontend build
- [x] Full 10-stage end-to-end workflow validation (`backend/tests/test_e2e_workflow_and_hardening.py`):
  - Verified scheduler disabled state detection
  - Verified manual discovery via API with normalization and persistence
  - Verified deterministic eligibility evaluation and weighted scoring
  - Verified persistent match notification generation
  - Verified repeated discovery idempotency (zero duplicate jobs, zero duplicate notifications)
  - Verified run history inspection and sanitized source diagnostics
  - Verified notification mark-as-read and dismiss lifecycle
  - Verified application package preparation, resume version persistence, and bit-for-bit SHA-256 verification
  - Verified server-side safeguards: rejection of unapproved applications, rejection of stale/mismatched fingerprints, and strict disabling of real external submissions
- [x] Process crash and restart recovery:
  - Added `SchedulerService.recover_stale_runs()` to automatically detect orphaned `RUNNING` discovery records on application startup and transition them safely to `FAILED`
- [x] Stale matching invalidation:
  - Verified that material job mutations upon rediscovery mark previous `MatchScore` records as `is_latest=False` and preserve audit history
- [x] Database migration & schema safety (`backend/tests/test_migration_and_database_safety.py`):
  - Validated forward migration, pre-existing data preservation, backward downgrade, and re-upgrade on isolated disposable SQLite database
  - Fixed `backend/alembic/env.py` to respect dynamic database URLs provided via config
  - Validated foreign key `ON DELETE SET NULL` behavior for notifications when referenced jobs or runs are removed
  - Validated concurrent notification deduplication under simultaneous coroutines across separate sessions
- [x] Frontend test suite & production bundle validation:
  - 27 passed Vitest tests across 8 test suites
  - Clean TypeScript verification (`tsc`) and Vite production build (`npm run build`)
- [x] Total test coverage:
  - Backend suite: 130 passed tests (100% pass rate)
  - Resume integrity acceptance suite: 7 passed tests
  - Frontend suite: 27 passed tests
- [x] Operational documentation and startup guides updated in `README.md`

### Phase 9 — Personalized Job Search and Smart Alerts
- [x] Comprehensive architectural audit verifying candidate profile schemas, matching/eligibility services, source adapters, scheduler, notification models, and frontend client.
- [x] Search Preferences Model & Schema Evolution:
  - Added `search_preferences` and `notification_preferences` JSON columns to `CandidateProfile`.
  - Added `config_json`, `last_status`, `last_error_summary`, and `jobs_discovered_count` to `JobSource`.
  - Created and applied Alembic revision `5e29f8a31c4d`.
  - Validated strict separation between search preferences (desired skills, role keywords) and candidate verified profile facts. Desired skills are never treated as candidate facts or injected into resumes.
  - Enhanced deterministic scoring with explainable preference contributions (target titles, role keywords, preferred companies bonus, excluded companies penalty, remote preference, and non-assumed salary satisfaction).
  - Preserved hard eligibility safeguards: high preference alignment can never override deterministic disqualification.
- [x] Job Source Configuration & Health Diagnostics:
  - Configurable board identifiers for Greenhouse and Lever adapters via API (`GET /api/v1/jobs/sources/{identifier}`, `PUT /api/v1/jobs/sources/{identifier}`).
  - Strict input validation restricting identifiers to alphanumeric, hyphen, and underscore characters (`^[a-zA-Z0-9_\-]+$`), blocking arbitrary URLs or SSRF vectors.
  - Granular source health metrics: enabled/disabled state, `last_run_at`, `last_status` (`HEALTHY`, `PARTIAL`, `FAILED`, `IDLE`), `jobs_discovered_count`, and sanitized `last_error_summary`.
- [x] Optional Email Notifications & Smart Alerts:
  - Implemented `EmailService` supporting `mock`, `console`, and `smtp` providers with bounded exponential retries.
  - Disabled by default (`EMAIL_NOTIFICATIONS_ENABLED=False`) with zero secrets stored in the database or exposed via APIs.
  - Immediate match alerts and configurable digest modes (`IMMEDIATE`, `DAILY_DIGEST`, `WEEKLY_DIGEST`).
  - Score threshold filtering (`min_match_score`), notifying only for eligible jobs meeting or exceeding candidate threshold.
  - Cryptographic match deduplication (`email_match:<candidate_id>:<job_id>`) preventing redundant emails across scheduler runs or restarts.
  - Resilient error handling: provider failures record sanitized diagnostic errors without losing or failing the persistent in-app notification.
  - Safe test-delivery endpoint (`POST /api/v1/notifications/test-email`) with real provider status reporting.
- [x] Frontend Integration:
  - Added `SearchPreferencesCard.tsx` with role keywords, desired skills, experience bounds, remote preferences, salary floor, and company filters.
  - Added `DiscoverySourcesCard.tsx` in Scheduler management with live source health badges, enabled/disabled toggles, board identifier configuration, and expandable diagnostics.
  - Added `NotificationSettingsModal.tsx` in Notification Center with email configuration status, threshold slider, delivery mode selector, channel toggles, and safe test email workflow.
  - Extended typed API client (`api.profile.getPreferences`, `updatePreferences`, `api.jobs.getSource`, `updateSource`, `api.notifications.getPreferences`, `updatePreferences`, `getEmailStatus`, `sendTestEmail`).
- [x] Full Regression Verification:
  - Backend suite: 139 passed tests (100% pass rate) across 17 test modules.
  - Resume version acceptance suite: 7 passed tests.
  - Frontend Vitest suite: 34 passed tests across 9 test suites.
  - Clean TypeScript compilation and production Vite build.

### Phase 10 — Notification Delivery Reliability and Digest Scheduling
- [x] Comprehensive architectural audit verifying email delivery semantics, idempotency, retry bounds, digest membership, scheduler integration, and frontend components.
- [x] Correct Delivery Status Semantics:
  - Discontinued misleading `DELIVERED` status for local test/mock dispatches.
  - Explicit status classifications: `SIMULATED` for mock/console providers (no external network handoff), `SENT` for RFC 5321 SMTP relay acceptance, `PENDING`/`QUEUED` for queued items, and `FAILED` for delivery errors.
  - Never claims SMTP relay acceptance guarantees final recipient inbox delivery.
  - Structured attempt tracking persisted in `metadata_json["attempts"]` with sanitized error summaries and timestamps.
- [x] Timezone-Aware Daily and Weekly Digests:
  - Implemented `DigestService` resolving candidate timezone preference with fallback to `settings.TIMEZONE` ("UTC") via standard library `zoneinfo.ZoneInfo`.
  - Deterministic schedule calculations for daily (09:00 AM local) and weekly (Monday 09:00 AM local) digests.
  - Added database migration `c821a4f02b9e` adding `digest_id` (foreign key to `notifications.id`, ondelete `SET NULL`) and `digested_at` to `notifications`.
  - Atomically marks covered in-app notifications upon successful digest dispatch (`SENT` or `SIMULATED`), ensuring previously digested items are never duplicated.
  - If digest delivery fails (`FAILED`), in-app notifications remain unlinked and available for retry.
  - Missed digest window recovery: detects missed digest windows following process downtime and executes catch-up without duplicate deliveries.
  - Concurrency safety: guarded with `_digest_lock` to prevent overlapping runs.
- [x] Scheduler Integration:
  - Registered `scheduled_digest_job` in `SchedulerService` running every 15 minutes to evaluate due digests across all active candidate profiles.
  - Integrated with scheduler pause/resume lifecycle and lifespan startup/shutdown.
- [x] Reliable Email Delivery & Bounded Retries:
  - Error classification via `is_permanent_smtp_error`: permanent failures (`SMTPAuthenticationError`, `SMTPSenderRefused`, `SMTPRecipientsRefused`, 5xx codes) abort immediately with zero retries.
  - Transient network failures (timeouts, disconnections) retry up to `EMAIL_MAX_RETRIES` with exponential backoff.
  - Zero credential persistence in database or API responses.
  - Email failures never roll back job discovery, score persistence, or in-app notification creation.
- [x] API Endpoints:
  - `GET /api/v1/notifications/digest/status`: returns digest configuration, next scheduled time, pending match count, and last digest status.
  - `POST /api/v1/notifications/digest/trigger`: manual test/catch-up trigger with `force` parameter.
  - `GET /api/v1/notifications/delivery-history`: returns recent delivery records with attempt counts, real status badges, and actionable errors.
- [x] Dashboard Improvements:
  - Enhanced `NotificationSettingsModal.tsx` with provider semantics badge (`Simulated Mode` vs `SMTP Transport Ready`), preferred timezone selector, scheduled digest telemetry card (next run, pending count, trigger action), and recent delivery history table.
  - Enhanced `NotificationCenter.tsx` with dedicated icon mapping for `DIGEST` notification type.
- [x] Full Verification:
  - Backend test suite: 149 passed tests (100% pass rate) across 18 test modules, including 10 deterministic tests in `test_digest_and_delivery_reliability.py`.
  - Resume integrity acceptance suite: 11 passed tests.
  - Frontend Vitest suite: 37 passed tests (100% pass rate) across 10 test modules, including 3 UI tests in `digest-and-delivery.test.tsx`.
  - Clean TypeScript compilation (`tsc`) and production Vite build (`npm run build`).



### Phase 11 — Job-Matching Quality and Search Intelligence
- [x] Comprehensive repository audit:
  - Validated scoring weights, deterministic eligibility gating, and explanation structures.
  - Identified cross-source deduplication limitations, update semantics, and freshness fields.
  - Verified application-history integrity, approval fingerprints, and immutable resume checksum preservation.
- [x] Conservative Cross-Source Duplicate Detection:
  - Implemented DuplicateDetectionService with staged evaluation:
    1. Canonical URL / career-page identifier exact matching (low-cost, high-confidence).
    2. Normalized blocking on employer name tokens, normalized job title, and location/remote compatibility.
    3. Multi-signal similarity scoring (company token overlap, title fuzzy similarity, remote/location match, description token Jaccard similarity) bounded by explicit thresholds:
       - High confidence (score >= 0.85).
       - Possible duplicate (score >= 0.65).
       - Insufficient evidence (< 0.65, distinct jobs preserved).
  - Explicit penalties against false merges: distinct physical locations apply a -0.35 deduction, preserving separate vacancies.
  - Non-destructive JobDuplicateCluster model: original jobs, sources, external IDs, and application foreign keys are preserved. Zero silent application transfers.
  - Concurrency safety: atomic database transactions and unique/locking guards prevent duplicate cluster creation.
  - Safe duplicate review API & UI: allows users to confirm or dismiss suspected duplicates (CONFIRMED, DISMISSED).
- [x] Job Freshness and Expiration Management:
  - Extended Job model with posted_at, first_seen_at, last_seen_at, freshness_status (ACTIVE, POTENTIALLY_STALE, CONFIRMED_CLOSED, UNKNOWN), freshness_reason, and last_verified_at.
  - Implemented JobFreshnessService:
    - Tracks verification timestamps separately from original posting dates.
    - Explicit state transitions: evaluate_staleness marks jobs unseen for > 30 days as POTENTIALLY_STALE.
    - Authoritative closure (mark_closed): only source-authoritative closure signals transition jobs to CONFIRMED_CLOSED.
    - Source failure isolation: network or adapter failures never mark jobs closed or stale.
    - Reactivation: previously closed jobs are authoritatively reactivated to ACTIVE upon authoritative rediscovery.
    - Safe archival: historical application records, match histories, and resume versions are never deleted.
- [x] Explainable Ranking Improvements & Policy Versioning:
  - Retained deterministic eligibility filter as a strict gate: DISQUALIFIED jobs can never be overridden by matching scores or user feedback.
  - Policy Versioning: explicitly bumped scoring policy version to 1.1.0.
  - Enriched ScoreBreakdown and MatchEvaluationResult with structured lists:
    - positive_contributions: itemized bonuses (verified skill match, title alignment, remote preference, preferred company, user feedback).
    - negative_contributions: itemized penalties (missing required skills, excluded company, stale listing penalty -10, confirmed closed penalty -40, negative feedback).
    - missing_information: flagged unknowns (salary missing, experience missing, remote status unspecified).
    - freshness_warnings and duplicate_warnings.
    - feedback_adjustment.
  - Deterministic bounded scoring in range [0, 100].
- [x] Candidate User Feedback Loop:
  - Implemented JobFeedback model with unique constraint on (candidate_id, job_id).
  - Supported feedback types: RELEVANT, NOT_RELEVANT, ALREADY_APPLIED, NOT_INTERESTED, DUPLICATE_LISTING.
  - Idempotent upsert, retrieval, and deletion operations via FeedbackService.
  - Feedback influences ranking deterministically via documented modifiers (+0.10 for Relevant, -0.25 for Not Relevant, -0.50 for Already Applied, -0.40 for Not Interested, -0.30 for Duplicate Listing).
  - Feedback never mutates verified profile facts or overrides hard eligibility constraints.
- [x] Offline Ranking Evaluation Framework:
  - Benchmark test fixtures in backend/app/evaluation/fixtures.py: candidate profile with 12 graded job listings representing strong, weak, disqualified, stale, closed, duplicate, and feedback-adjusted cases.
  - Evaluation metrics in backend/app/evaluation/metrics.py:
    - Ranking metrics: Precision@K, Recall@K, NDCG@K using graded relevance labels.
    - Duplicate detection metrics: Precision, Recall, F1 score.
    - Freshness accuracy: Classification accuracy against ground truth.
  - Reproducible CLI runner: backend/evaluation/run_ranking_eval.py outputting machine-readable JSON to storage/evaluation_results.json.
  - Benchmark performance: Precision@3: 1.0, NDCG@3: 1.0, Duplicate F1: 1.0, Freshness Accuracy: 1.0.
- [x] Database Schema Migration:
  - Created and applied Alembic revision d934b51c8a2f (job_duplicate_clusters, job_feedbacks, freshness columns on jobs).
- [x] API Endpoints:
  - GET /api/v1/jobs/duplicates: List active duplicate clusters.
  - POST /api/v1/jobs/duplicates/{id}/review: Review and confirm or dismiss clusters.
  - GET /api/v1/jobs/{id}/freshness: Inspect job freshness status and verification timestamps.
  - POST /api/v1/jobs/{id}/feedback: Submit or update candidate feedback.
  - GET /api/v1/jobs/{id}/feedback: Retrieve current candidate feedback for a job.
  - DELETE /api/v1/jobs/{id}/feedback: Remove feedback.
  - POST /api/v1/matching/evaluate-ranking: Trigger offline ranking evaluation and return quality metrics.
- [x] Frontend Dashboard Extensions:
  - Updated typed API client in frontend/src/lib/api-client.ts.
  - Added DuplicateClustersModal.tsx for reviewing and managing cross-source duplicates.
  - Added RankingEvaluationModal.tsx for development offline evaluation metrics and benchmark inspection.
  - Enriched JobDetailModal.tsx with freshness badges, duplicate indicators, interactive feedback buttons (Relevant, Not Relevant, Already Applied, Not Interested, Duplicate), and positive/negative contribution breakdowns.
  - Enriched JobsList.tsx with duplicate and ranking evaluation header buttons, card freshness badges, and duplicate cluster badges.
- [x] Full Regression Verification:
  - 164 passed backend tests across 22 test modules (100% pass rate).
  - 41 passed frontend Vitest tests across 11 test files (100% pass rate).
  - Clean TypeScript compilation (tsc) and production Vite build.

### Phase 12 — Production Readiness and Live-Source Validation
- [x] Baseline Audit and Inspection:
  - Validated Git status, Alembic migration history, configuration, source adapters, discovery pipeline, matching services, duplicate detection, freshness tracking, feedback, notifications, resume integrity, and application workflow.
  - Baseline tests: 164 backend tests passed, 41 frontend tests passed, offline ranking evaluation succeeded.
- [x] Live-Source Integration Validation and Adapter Hardening:
  - Extended BaseJobSourceAdapter with check_job_status probe method and SourceRateLimitException.
  - Greenhouse Adapter:
    - Added HTTP 429 rate limit detection and dynamic Retry-After header backoff parsing.
    - Added result limit parameter to Greenhouse API requests.
    - Added structured salary extraction from job custom metadata and description text patterns.
    - Added ISO-8601 posted_at normalization from updated_at.
    - Added check_job_status single-job probe endpoint to verify active vs closed status directly from public Greenhouse board API.
  - Lever Adapter:
    - Added HTTP 429 rate limit detection and Retry-After header backoff parsing.
    - Added native limit parameter to Lever API requests.
    - Added structured salary extraction from salaryRange and salaryDescription.
    - Added Unix epoch milliseconds posted_at normalization from createdAt.
    - Added workplaceType normalization (remote, hybrid, on-site).
    - Added check_job_status single-job probe endpoint for public Lever boards.
  - Synthetic Adapter:
    - Added check_job_status probe support and posted_at timestamps for regression tests.
  - Live vs Mock Separation:
    - Dedicated test module tests/test_live_sources_and_adapters.py with comprehensive error handling (429, 500, timeout, malformed responses).
    - If a live network source is unavailable, status probes report UNKNOWN / unverified rather than claiming success.
- [x] Live Freshness Verification Service & UI:
  - Implemented JobFreshnessService.verify_job_live_status to probe job source adapters directly.
  - Added POST /api/v1/jobs/{job_id}/freshness/verify endpoint.
  - Added 'Verify Live Status' button with loading and real-time freshness telemetry in JobDetailModal.tsx and updated api.jobs.verifyFreshness.
- [x] Data Quality and Recommendation Regression Suite:
  - Created tests/test_data_quality_and_ranking_regressions.py:
    - Case-sensitive URL paths preserved during canonicalization.
    - Distinct vacancies with similar titles never merged if locations/employers differ.
    - Source outages isolate gracefully without marking listings as closed.
    - Deterministic eligibility disqualification (e.g. US citizenship) strictly wins over positive user feedback.
    - Startup configuration safety validation enforces local security boundaries.
- [x] Database Schema Migration and Query Performance:
  - Added database indexes on jobs.canonical_url and jobs.discovered_at to prevent full-table scans during discovery and duplicate candidate matching.
  - Created and cleanly applied Alembic revision e145f6789abc (revising d934b51c8a2f). Alembic head is now e145f6789abc.
  - Fixed candidate blocking filters and offset-naive vs offset-aware datetime comparisons in DuplicateDetectionService.
- [x] Configuration & Operational Security:
  - Added validate_startup_configuration() to Settings, invoked during FastAPI lifespan startup:
    - Strictly enforces JOBPILOT_REAL_SUBMISSION_ENABLED = False for local execution.
    - Warns and logs safeguards if APP_HOST is non-localhost.
    - Validates mandatory local storage directories (storage/resumes, storage/screenshots).
    - Validates SMTP settings and logs mock email provider status.
- [x] 12-Stage End-to-End Acceptance Flow:
  - Implemented tests/test_production_readiness_e2e.py validating:
    1. Candidate profile creation.
    2. Supported source configuration.
    3. Discovery pipeline execution.
    4. Normalized job and source health verification.
    5. Deterministic eligibility and matching.
    6. Score breakdown explanations and freshness tracking.
    7. Cross-source duplicate detection and review.
    8. User feedback recording and revision.
    9. In-app notification creation.
    10. Mock email notification delivery.
    11. Resume PDF generation, atomic SHA-256 storage, and bit-for-bit file integrity verification.
    12. Application preparation, canonical SHA-256 fingerprint approval, and safety gate blocking external execution.
- [x] Final Test & Quality Validation:
  - Backend test suite: 175 passed tests across 25 test modules (100% pass rate).
  - Frontend test suite: 41 passed Vitest tests across 11 test files (100% pass rate).
  - TypeScript compilation (tsc) and Vite production build passed without errors.
  - Offline ranking evaluation: Precision@3 = 1.0, NDCG@3 = 1.0, Duplicate F1 = 1.0, Freshness Accuracy = 1.0.
