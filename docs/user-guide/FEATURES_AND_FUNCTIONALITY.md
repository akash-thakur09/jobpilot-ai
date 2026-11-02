# JobPilot AI — Complete Feature Inventory & Functional Reference

This document provides a comprehensive inventory of all implemented features across Phases 0–12 of JobPilot AI, grounded directly in the codebase.

---

## Feature Index

1. [Dashboard and Overview Screen](#1-dashboard-and-overview-screen)
2. [Candidate Profile Management](#2-candidate-profile-management)
3. [Master Resume Import and Text Extraction](#3-master-resume-import-and-text-extraction)
4. [Verified Skills, Experience, Education, and Projects](#4-verified-skills-experience-education-and-projects)
5. [Job Source Configuration & Health Diagnostics](#5-job-source-configuration--health-diagnostics)
6. [Job Discovery & Ingestion Pipeline](#6-job-discovery--ingestion-pipeline)
7. [Greenhouse Job Board Integration](#7-greenhouse-job-board-integration)
8. [Lever Postings Integration](#8-lever-postings-integration)
9. [Synthetic Job Source](#9-synthetic-job-source)
10. [Job Normalization and Canonical Persistence](#10-job-normalization-and-canonical-persistence)
11. [Cross-Source Deduplication & Cluster Review](#11-cross-source-deduplication--cluster-review)
12. [Job Freshness Lifecycle & Live Status Verification](#12-job-freshness-lifecycle--live-status-verification)
13. [Deterministic Eligibility Evaluation](#13-deterministic-eligibility-evaluation)
14. [Explainable Match Scoring (Policy 1.1.0)](#14-explainable-match-scoring-policy-110)
15. [Match Breakdown & Positive/Negative Contributions](#15-match-breakdown--positivenegative-contributions)
16. [Search Preferences and Company Exclusions](#16-search-preferences-and-company-exclusions)
17. [Candidate Relevance Feedback Loop](#17-candidate-relevance-feedback-loop)
18. [Zero-Hallucination Resume Tailoring](#18-zero-hallucination-resume-tailoring)
19. [ATS-Friendly PDF Generation and Validation](#19-ats-friendly-pdf-generation-and-validation)
20. [Resume Versioning and SHA-256 Checksum Validation](#20-resume-versioning-and-sha-256-checksum-validation)
21. [Application Preparation & Review Queue](#21-application-preparation--review-queue)
22. [Cryptographic Approval Fingerprinting](#22-cryptographic-approval-fingerprinting)
23. [Browser Automation & Synthetic Test Harness](#23-browser-automation--synthetic-test-harness)
24. [Application State Machine & Append-Only Audit History](#24-application-state-machine--append-only-audit-history)
25. [Application Outcome Reconciliation](#25-application-outcome-reconciliation)
26. [In-App Persistent Notifications](#26-in-app-persistent-notifications)
27. [Email Notification Configuration](#27-email-notification-configuration)
28. [Timezone-Aware Daily and Weekly Digests](#28-timezone-aware-daily-and-weekly-digests)
29. [Scheduled Background Discovery](#29-scheduled-background-discovery)
30. [Scheduler Telemetry, Interval Updates, & Crash Recovery](#30-scheduler-telemetry-interval-updates--crash-recovery)
31. [Offline Ranking Evaluation Benchmark Runner](#31-offline-ranking-evaluation-benchmark-runner)
32. [Configuration Management and Safe Defaults](#32-configuration-management-and-safe-defaults)
33. [Health Endpoints & Operational Diagnostics](#33-health-endpoints--operational-diagnostics)
34. [Operational Security Safeguards & Submission Boundaries](#34-operational-security-safeguards--submission-boundaries)

---

### 1. Dashboard and Overview Screen
- **Business Purpose**: Provides an executive control center summarizing discovery volume, eligible roles, pending approvals, and scheduler status.
- **Problem Solved**: Eliminates fragmented tracking across multiple browser tabs and spreadsheets.
- **Frontend Location**: Home screen `/` (`DashboardOverview.tsx`).
- **Backend APIs**:
  - `GET /api/v1/jobs?limit=1`
  - `GET /api/v1/matching/results?is_eligible=true`
  - `GET /api/v1/applications?status=READY_FOR_REVIEW`
  - `GET /api/v1/applications?status=OUTCOME_UNKNOWN`
  - `GET /api/v1/scheduler/status`
- **Models Involved**: `Job`, `MatchScore`, `Application`, `AutomationRun`.
- **Inputs/Outputs**: Displays 4 metric telemetry cards, an actionable unknown outcome warning banner, and recent discovery activity.
- **What Happens Internally**: On component mount, the frontend dispatches parallel async requests via the typed API client, aggregating live entity counts directly from SQLite.
- **Verification Status**: **Verified in Code & Runtime** (`DashboardOverview.test.tsx`, 3 passed tests).
- **Limitations**: Displays total counts; does not render historical metric trend charts.

---

### 2. Candidate Profile Management
- **Business Purpose**: Stores your verified career history, contact details, work authorization, and target criteria.
- **Problem Solved**: Provides a single source of truth for all downstream matching and resume compilation.
- **Frontend Location**: **Candidate Profile** tab (`CandidateProfileView.tsx`).
- **Backend APIs**:
  - `GET /api/v1/profile`
  - `POST /api/v1/profile`
  - `PATCH /api/v1/profile`
- **Models & Services**: `CandidateProfile` model, `CandidateService`.
- **Inputs/Outputs**: Name, email, phone, location, work authorization (`US_CITIZEN`, `GREEN_CARD`, `H1B`, `OTHER`), years of experience, target titles, target salary.
- **Verification Status**: **Verified in Code & Runtime** (`test_candidate_profile.py`, live API tested).
- **Limitations**: Single-candidate only; no multi-profile switching in UI.

---

### 3. Master Resume Import and Text Extraction
- **Business Purpose**: Extracts structured facts from your existing PDF resume to bootstrap your profile.
- **Problem Solved**: Saves you from manually typing out your entire work history.
- **Frontend Location**: Upload button in `CandidateProfileView.tsx`.
- **Backend APIs**:
  - `POST /api/v1/profile/resume/import`
  - `POST /api/v1/profile/resume/confirm`
- **Models & Services**: `ResumeParserService`, `pypdf`.
- **Internal Behavior**: Validates PDF file header, extracts plain text using `pypdf`, identifies sections (Experience, Skills, Education), rejects corrupt or password-protected files, and stages parsed entities for candidate confirmation.
- **Verification Status**: **Verified in Code & Runtime** (`test_resume_import.py`, 6 passed tests).
- **Limitations**: Standard single-column PDFs parse best; complex graphical multi-column layouts may produce unordered text blocks.

---

### 4. Verified Skills, Experience, Education, and Projects
- **Business Purpose**: Segregates verified candidate facts from aspirational desires.
- **Problem Solved**: Prevents AI hallucination during resume generation.
- **Frontend Location**: Subsections in `CandidateProfileView.tsx`.
- **Backend APIs**:
  - `POST/DELETE /api/v1/profile/skills`
  - `POST/DELETE /api/v1/profile/experiences`
  - `POST/DELETE /api/v1/profile/educations`
  - `POST/DELETE /api/v1/profile/projects`
- **Models & Services**: `CandidateSkill`, `CandidateExperience`, `CandidateEducation`, `CandidateProject`.
- **Verification Status**: **Verified in Code & Runtime** (`test_candidate_profile.py`).
- **Limitations**: Skills must have `is_verified=True` to be included in tailored resumes.

---

### 5. Job Source Configuration & Health Diagnostics
- **Business Purpose**: Manages integration settings and tracks operational health for external career boards.
- **Problem Solved**: Prevents discovery failures from silent configuration drift or rate limits.
- **Frontend Location**: **Scheduler & Discovery Sources** card (`DiscoverySourcesCard.tsx`).
- **Backend APIs**:
  - `GET /api/v1/jobs/sources`
  - `GET /api/v1/jobs/sources/{identifier}`
  - `PUT /api/v1/jobs/sources/{identifier}`
- **Models & Services**: `JobSource` model, `JobDiscoveryService`.
- **Inputs/Outputs**: Board identifier token, enabled/disabled state, `last_status` (`HEALTHY`, `ERROR`), `jobs_discovered_count`, `last_error_summary`.
- **Input Security**: Tokens strictly validated against `^[a-zA-Z0-9_\-]+$`, blocking arbitrary URLs and SSRF vectors.
- **Verification Status**: **Verified in Code & Runtime** (`test_source_configuration.py`, live API tested).
- **Limitations**: Only alphanumeric/hyphen board identifiers are permitted; arbitrary domains cannot be added.

---

### 6. Job Discovery & Ingestion Pipeline
- **Business Purpose**: Core pipeline orchestrating job fetching, normalization, deduplication, matching, and notifications.
- **Problem Solved**: Coordinates the multi-step ingest workflow without blocking other system operations.
- **Backend APIs**: `POST /api/v1/scheduler/run`.
- **Models & Services**: `DiscoveryMatchingPipeline`, `AutomationRun`, `ADAPTER_REGISTRY`.
- **Internal Behavior**: Creates persistent `AutomationRun` record; iterates requested sources under concurrency semaphore; normalizes listings; persists new records; clusters duplicates; evaluates candidate eligibility; dispatches match notifications; finalizes run telemetry.
- **Verification Status**: **Verified in Code & Runtime** (`test_discovery_pipeline.py`, live API tested).
- **Limitations**: In-process execution; multi-worker gunicorn setups require disabling the scheduler on all but one worker.

---

### 7. Greenhouse Job Board Integration
- **Business Purpose**: Ingests active vacancies from public Greenhouse career portals.
- **Problem Solved**: Direct company-board access without intermediary aggregators.
- **Backend APIs**: `GreenhouseJobAdapter` (`backend/app/collectors/greenhouse.py`).
- **Endpoints Queried**:
  - List jobs: `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`
  - Single-job probe: `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{id}`
- **Rate Limits & Backoff**: 30 RPM default; detects HTTP 429 and parses `Retry-After` header.
- **Verification Status**: **Verified in Code & Runtime** (`test_live_sources_and_adapters.py`, live network verified on `canonical`).
- **Limitations**: Requires an active employer board token (e.g. `canonical`, `stripe`). Private postings are inaccessible.

---

### 8. Lever Postings Integration
- **Business Purpose**: Ingests postings from public Lever career sites.
- **Problem Solved**: Accesses venture-backed tech startups and scale-ups using Lever ATS.
- **Backend APIs**: `LeverJobAdapter` (`backend/app/collectors/lever.py`).
- **Endpoints Queried**:
  - List postings: `https://api.lever.co/v0/postings/{site_token}?mode=json`
  - Single-job probe: `https://api.lever.co/v0/postings/{site_token}/{id}`
- **Rate Limits & Backoff**: 30 RPM default; HTTP 429 detection and backoff.
- **Verification Status**: **Verified in Code & Runtime** (`test_live_sources_and_adapters.py`, live network verified on `leverdemo`).
- **Limitations**: Requires a valid employer site token.

---

### 9. Synthetic Job Source
- **Business Purpose**: Built-in deterministic job fixture emitting diverse vacancies for offline testing.
- **Problem Solved**: Allows full pipeline, matching, and UI testing without internet access.
- **Backend APIs**: `SyntheticJobAdapter` (`backend/app/collectors/synthetic.py`).
- **Verification Status**: **Verified in Code & Runtime** (`test_job_discovery.py`).
- **Limitations**: Emits synthetic dummy data; not intended for real job applications.

---

### 10. Job Normalization and Canonical Persistence
- **Business Purpose**: Converts heterogenous external payloads into a uniform `Job` record.
- **Problem Solved**: Standardizes titles, compensation numbers, and locations across different ATS formats.
- **Models & Services**: `NormalizedJob`, `Job` model, `JobDiscoveryService`.
- **Key Rules**:
  - Preserves case sensitivity in URL paths while lowercasing hostnames.
  - Cleans HTML markup from job descriptions.
  - Extracts salary numbers from metadata or text patterns.
- **Verification Status**: **Verified in Code & Runtime** (`test_data_quality_and_ranking_regressions.py`).

---

### 11. Cross-Source Deduplication & Cluster Review
- **Business Purpose**: Identifies identical job vacancies posted across multiple boards or aggregators.
- **Problem Solved**: Prevents candidates from applying twice to the same job opening.
- **Frontend Location**: Duplicate group badges in `JobsList.tsx` and review modal `DuplicateClustersModal.tsx`.
- **Backend APIs**:
  - `GET /api/v1/jobs/duplicates`
  - `POST /api/v1/jobs/duplicates/{id}/review`
- **Models & Services**: `JobDuplicateCluster`, `DuplicateDetectionService`.
- **Internal Behavior**: Multi-signal scoring (employer token overlap, title fuzzy match, description overlap). Explicit -0.35 penalty for conflicting physical locations.
- **Verification Status**: **Verified in Code & Runtime** (`test_duplicate_detection.py`, 4 Vitest UI tests).
- **Limitations**: Threshold-based; user can confirm or dismiss borderline clusters.

---

### 12. Job Freshness Lifecycle & Live Status Verification
- **Business Purpose**: Tracks whether a vacancy is active, stale, or authoritatively closed.
- **Problem Solved**: Stops candidates from wasting time on ghost jobs or expired listings.
- **Frontend Location**: Freshness badges and **Verify Live Status** button in `JobDetailModal.tsx`.
- **Backend APIs**:
  - `GET /api/v1/jobs/{id}/freshness`
  - `POST /api/v1/jobs/{id}/freshness/verify`
- **Models & Services**: `JobFreshnessService`, `FreshnessStatus` (`ACTIVE`, `POTENTIALLY_STALE`, `CONFIRMED_CLOSED`, `UNKNOWN`).
- **Internal Behavior**: Evaluates staleness (> 30 days unseen). Probes single-job URL directly; returns HTTP 200 → `ACTIVE`, HTTP 404 → `CONFIRMED_CLOSED`, timeout/error → `UNKNOWN`.
- **Verification Status**: **Verified in Code & Runtime** (`test_job_freshness.py`, live verified on Greenhouse/Lever).

---

### 13. Deterministic Eligibility Evaluation
- **Business Purpose**: Hard gate ensuring you only review jobs you can legally and physically accept.
- **Problem Solved**: Prevents emotional fatigue from pursuing unviable opportunities.
- **Frontend Location**: Eligibility badges (`Eligible`, `Disqualified`, `Needs Review`) on all job cards.
- **Backend APIs**: Evaluated within `POST /api/v1/matching/evaluate/{job_id}`.
- **Models & Services**: `EligibilityService`, `EligibilityStatus`.
- **Rules Enforced**: Work authorization (e.g. citizenship), location/remote compatibility, minimum years of experience, and mandatory skills.
- **Verification Status**: **Verified in Code & Runtime** (`test_matching_engine.py`).
- **Safety Rule**: High match scores or candidate feedback can **never** override a `DISQUALIFIED` status.

---

### 14. Explainable Match Scoring (Policy 1.1.0)
- **Business Purpose**: Calculates an audit-friendly score from 0 to 100 indicating fit.
- **Problem Solved**: Replaces opaque AI black boxes with clear scoring rules.
- **Models & Services**: `DeterministicScoringService`, `MatchScore` model.
- **Weight Breakdown**:
  - Skills: 40%
  - Title Relevance: 20%
  - Experience: 15%
  - Projects: 10%
  - Location/Remote: 10%
  - Salary: 5%
- **Verification Status**: **Verified in Code & Runtime** (`test_matching_engine.py`, `test_feedback_and_explainable_scoring.py`).

---

### 15. Match Breakdown & Positive/Negative Contributions
- **Business Purpose**: Shows itemized reasons why a job scored well or poorly.
- **Problem Solved**: Helps you decide whether an opportunity is worth pursuing.
- **Frontend Location**: **Score Breakdown** section in `JobDetailModal.tsx`.
- **Verification Status**: **Verified in Code & Runtime**.

---

### 16. Search Preferences and Company Exclusions
- **Business Purpose**: Tunes matching criteria according to personal preferences without mutating verified facts.
- **Problem Solved**: Allows you to exclude toxic employers or prioritize favorite companies.
- **Frontend Location**: `SearchPreferencesCard.tsx`.
- **Backend APIs**: `GET/PUT /api/v1/profile/preferences`.
- **Verification Status**: **Verified in Code & Runtime** (`test_preferences_and_matching.py`).
- **Safety Boundary**: Desired skills in search preferences are strictly separated from verified facts and are **never** injected into resumes.

---

### 17. Candidate Relevance Feedback Loop
- **Business Purpose**: Lets you adjust ranking scores for specific listings.
- **Problem Solved**: Learns from your decisions to surface better matches.
- **Frontend Location**: Feedback buttons (`Relevant`, `Not Relevant`, `Already Applied`, `Not Interested`, `Duplicate`) in `JobDetailModal.tsx`.
- **Backend APIs**:
  - `POST /api/v1/jobs/{id}/feedback`
  - `GET /api/v1/jobs/{id}/feedback`
  - `DELETE /api/v1/jobs/{id}/feedback`
- **Models & Services**: `JobFeedback`, `FeedbackService`.
- **Modifiers Applied**: `RELEVANT` (+10%), `NOT_RELEVANT` (-25%), `ALREADY_APPLIED` (-50%), `NOT_INTERESTED` (-40%), `DUPLICATE` (-30%).
- **Verification Status**: **Verified in Code & Runtime** (`test_feedback_and_explainable_scoring.py`).

---

### 18. Zero-Hallucination Resume Tailoring
- **Business Purpose**: Generates a customized resume targeting the job description using only verified facts.
- **Problem Solved**: Guarantees you never present fabricated experience or skills to recruiters.
- **Backend APIs**: `POST /api/v1/resumes/generate`.
- **Models & Services**: `ResumeVersionService`, `ResumeFactValidator`.
- **Internal Behavior**: Parses job keywords; re-orders verified skills and experience bullets to emphasize matching technologies; validates every claim against `CandidateProfile`; aborts if any unverified claim is detected.
- **Verification Status**: **Verified in Code & Runtime** (`test_resume_tailoring.py`, 5 passed tests).

---

### 19. ATS-Friendly PDF Generation and Validation
- **Business Purpose**: Produces clean, parseable single-column PDF resumes.
- **Problem Solved**: Prevents ATS parsers from dropping columns, tables, or non-standard fonts.
- **Models & Services**: `ResumePdfRenderer` (ReportLab), `ResumePdfVerifier` (`pypdf`).
- **Internal Behavior**: Builds a single-column flowable document; extracts plain text using `pypdf`; checks character count, candidate name, email, and section headings.
- **Verification Status**: **Verified in Code & Runtime** (`test_resume_tailoring.py`).

---

### 20. Resume Versioning and SHA-256 Checksum Validation
- **Business Purpose**: Preserves an immutable, bit-for-bit audit trail of every generated resume.
- **Problem Solved**: Ensures you know the exact resume version submitted for every job.
- **Frontend Location**: `ResumeWorkspace.tsx`.
- **Backend APIs**:
  - `GET /api/v1/resumes/job/{job_id}`
  - `GET /api/v1/resumes/{id}/download`
  - `GET /api/v1/resumes/{id}/integrity`
- **Models & Services**: `ResumeVersion`, `ResumeStorageService`.
- **Verification Status**: **Verified in Code & Runtime** (`tests/acceptance/test_resume_version_integrity.py`, 7 passed tests).

---

### 21. Application Preparation & Review Queue
- **Business Purpose**: Prepares application data and stages it for human review.
- **Problem Solved**: Prevents accidental submissions by requiring explicit review.
- **Frontend Location**: `ApplicationQueue.tsx`.
- **Backend APIs**: `POST /api/v1/applications/prepare`.
- **Models & Services**: `ApplicationWorkflowService`, `Application` model.
- **Verification Status**: **Verified in Code & Runtime** (`test_applications_api.py`).

---

### 22. Cryptographic Approval Fingerprinting
- **Business Purpose**: Guarantees that the data approved by the human is identical to what is submitted.
- **Problem Solved**: Prevents bait-and-switch submissions if profile facts or job requirements change after review.
- **Models & Services**: `approval_fingerprint.py`.
- **Internal Behavior**: Generates a canonical SHA-256 hash over candidate facts, job fingerprint, resume checksum, and policy version. Any data mutation alters the fingerprint and rejects approval with HTTP 400.
- **Verification Status**: **Verified in Code & Runtime** (`test_application_workflow_service.py`).

---

### 23. Browser Automation & Synthetic Test Harness
- **Business Purpose**: Provides browser form-filling automation capabilities for testing application workflows safely.
- **Problem Solved**: Tests form fill and document upload mechanics without submitting real applications.
- **Backend APIs**: `POST /api/v1/applications/{id}/attempt`.
- **Models & Services**: `BrowserAutomationRunner`, Playwright adapter, local mock portal.
- **Safety Boundary**: Restricted to localhost synthetic test harnesses (`127.0.0.1`). Real external URLs are blocked with HTTP 400.
- **Verification Status**: **Verified in Code & Runtime** (`test_browser_automation.py`).

---

### 24. Application State Machine & Append-Only Audit History
- **Business Purpose**: Governs legal status transitions and logs audit events.
- **Problem Solved**: Prevents inconsistent application states.
- **Frontend Location**: Timeline view in `ApplicationQueue.tsx`.
- **Backend APIs**: `GET /api/v1/applications/{id}/events`.
- **Models & Services**: `ApplicationStateMachine`, `ApplicationEvent`, `SubmissionAttempt`.
- **Permitted States**: `PREPARING` → `READY_FOR_REVIEW` → `APPROVED` → `SUBMITTING` → `SUBMITTED` (or `SUBMISSION_FAILED`).
- **Verification Status**: **Verified in Code & Runtime** (`test_application_state_machine.py`, 12 passed tests).

---

### 25. Application Outcome Reconciliation
- **Business Purpose**: Updates application records following external employer actions.
- **Problem Solved**: Keeps your job search history synchronized with real-world outcomes.
- **Frontend Location**: Reconcile action buttons in `ApplicationQueue.tsx`.
- **Backend APIs**: `POST /api/v1/applications/{id}/reconcile`.
- **Outcomes Supported**: `INTERVIEWING`, `OFFER_RECEIVED`, `REJECTED`, `WITHDRAWN`, `CONFIRMED_SUBMITTED`.
- **Verification Status**: **Verified in Code & Runtime** (`test_applications_api.py`).

---

### 26. In-App Persistent Notifications
- **Business Purpose**: Alerts you to new eligible job matches and system events.
- **Problem Solved**: Keeps you informed without requiring email setup.
- **Frontend Location**: Notification popover badge in workspace header (`NotificationCenter.tsx`).
- **Backend APIs**:
  - `GET /api/v1/notifications`
  - `PATCH /api/v1/notifications/{id}/read`
  - `POST /api/v1/notifications/mark-all-read`
  - `DELETE /api/v1/notifications/{id}`
- **Models & Services**: `Notification`, `NotificationService`.
- **Verification Status**: **Verified in Code & Runtime** (`test_notifications.py`, 3 Vitest tests).

---

### 27. Email Notification Configuration
- **Business Purpose**: Sends alerts to your personal inbox.
- **Problem Solved**: Provides notifications when you are away from your computer.
- **Frontend Location**: `NotificationSettingsModal.tsx`.
- **Backend APIs**:
  - `GET /api/v1/notifications/email-status`
  - `POST /api/v1/notifications/test-email`
- **Models & Services**: `EmailService` (`mock`, `console`, `smtp`).
- **Verification Status**: **Verified in Code & Runtime** (`test_email_notifications.py`).
- **Configuration**: Disabled by default (`EMAIL_NOTIFICATIONS_ENABLED=false`).

---

### 28. Timezone-Aware Daily and Weekly Digests
- **Business Purpose**: Aggregates eligible job matches into scheduled digest summaries.
- **Problem Solved**: Avoids notification overload by batching updates.
- **Backend APIs**:
  - `GET /api/v1/notifications/digest/status`
  - `POST /api/v1/notifications/digest/trigger`
- **Models & Services**: `DigestService`, `zoneinfo.ZoneInfo`.
- **Internal Behavior**: Computes local schedule (e.g. 09:00 AM local time or Mondays at 09:00 AM). Atomically links covered notifications via `digest_id` to prevent duplicates.
- **Verification Status**: **Verified in Code & Runtime** (`test_digest_and_delivery_reliability.py`, 10 passed tests).

---

### 29. Scheduled Background Discovery
- **Business Purpose**: Periodically discovers new job openings automatically.
- **Problem Solved**: Eliminates the need to trigger manual discovery runs every day.
- **Backend APIs**: `APScheduler` `AsyncIOScheduler` running in FastAPI lifespan.
- **Configuration**: `SCHEDULER_ENABLED=false` by default; interval configurable from 5 to 10,080 minutes.
- **Verification Status**: **Verified in Code & Runtime** (`test_scheduler.py`).

---

### 30. Scheduler Telemetry, Interval Updates, & Crash Recovery
- **Business Purpose**: Controls background scheduler execution and recovers from unexpected termination.
- **Problem Solved**: Ensures the scheduler recovers cleanly if your machine goes to sleep or reboots.
- **Frontend Location**: `SchedulerManager.tsx`.
- **Backend APIs**:
  - `GET /api/v1/scheduler/status`
  - `POST /api/v1/scheduler/config`
  - `GET /api/v1/scheduler/runs`
- **Recovery Mechanism**: `SchedulerService.recover_stale_runs()` reclaims orphaned `RUNNING` discovery jobs on startup and marks them `FAILED`.
- **Verification Status**: **Verified in Code & Runtime** (`test_scheduler.py`).

---

### 31. Offline Ranking Evaluation Benchmark Runner
- **Business Purpose**: Measures matching quality, duplicate detection, and freshness accuracy against a labeled benchmark.
- **Problem Solved**: Validates that ranking policy changes do not cause algorithmic regressions.
- **Frontend Location**: `RankingEvaluationModal.tsx`.
- **Backend APIs**:
  - `POST /api/v1/matching/evaluate-ranking`
  - CLI: `backend/evaluation/run_ranking_eval.py`
- **Metrics Tracked**: Precision@3, Precision@5, Recall@3, Recall@5, NDCG@3, NDCG@5, Duplicate F1, Freshness Accuracy.
- **Verification Status**: **Verified in Code & Runtime** (`test_ranking_evaluation.py`).

---

### 32. Configuration Management and Safe Defaults
- **Business Purpose**: Enforces secure, local-only defaults across all application settings.
- **Problem Solved**: Prevents credential leaks or unintended network exposure.
- **Implementation**: `Settings` in `backend/app/core/config.py` using `pydantic-settings`.
- **Key Defaults**: Loopback host `127.0.0.1`, `JOBPILOT_REAL_SUBMISSION_ENABLED=False`, local SQLite storage.
- **Verification Status**: **Verified in Code & Runtime** (`test_data_quality_and_ranking_regressions.py`).

---

### 33. Health Endpoints & Operational Diagnostics
- **Business Purpose**: Provides liveness and readiness probes for system monitoring.
- **Problem Solved**: Confirms service and database health before initiating discovery.
- **Endpoints**:
  - `GET /`: Status and navigational links.
  - `GET /health`: Basic ping probe (`status: ok`).
  - `GET /api/v1/health`: API subsystem status.
  - `GET /api/v1/health/ready`: Checks async SQLite database connectivity.
- **Verification Status**: **Verified in Code & Runtime** (`test_health.py`).

---

### 34. Operational Security Safeguards & Submission Boundaries
- **Business Purpose**: Protects you from unwanted external submissions and credential exposure.
- **Problem Solved**: Preserves ethical, safe software operation.
- **Enforcement Rules**:
  - `JOBPILOT_REAL_SUBMISSION_ENABLED` forced to `False` on startup.
  - External HTTP targets in automation runner rejected with HTTP 400.
  - Error messages scrub candidate secrets and sensitive stack traces.
  - Resumes validate bit-for-bit against recorded SHA-256 hashes before review.
- **Verification Status**: **Verified in Code & Runtime**.

