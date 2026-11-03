# 01 — Features & Implementation Status

This document provides a comprehensive inventory of every major functional module in **JobPilot AI**, mapping business purposes to actual source code files, frontend components, API endpoints, database entities, test suites, operational statuses, and known limitations.

---

## Status Legend
- **Implemented**: Fully functional, tested end-to-end, and integrated into frontend and backend.
- **Partially Implemented**: Core logic exists and works, but certain advanced features or external connectors are mock/stubbed.
- **Disabled**: Intentionally deactivated by default for safety, legal compliance, or local execution isolation.
- **Not Implemented**: Planned in roadmap but not present in code.

---

## Feature Matrix Summary

| Feature Area | Module | Operational Status | Primary Test Coverage |
| :--- | :--- | :--- | :--- |
| **Candidate Profile** | Master Resume Parsing & Facts Management | **Implemented** | `test_candidate_profile.py`, `test_resume_import.py` |
| **Search Preferences** | Career Preferences & INR LPA Compensation | **Implemented** | `test_search_preferences_persistence_and_salary.py` |
| **Job Discovery** | Multi-Source Job Discovery Engine | **Implemented** | `test_discovery_pipeline.py`, `test_job_discovery.py` |
| **Source Adapters** | Greenhouse & Lever Multi-Board Ingestion | **Implemented** | `test_multi_board_discovery.py`, `test_live_sources_and_adapters.py` |
| **Indian Job Sources** | Naukri, Instahyre, Cutshort, Foundit, Indeed | **Implemented** (Manual Import) | `test_indian_job_adapters.py`, `test_indian_job_discovery_integration.py` |
| **Indian Job Sources** | Hirist RSS/XML Feed & SSRF Security | **Implemented** (Config Feed) | `test_indian_job_discovery_integration.py` |
| **Indian Job Sources** | LinkedIn Alert & JSON Ingestion | **Implemented** (Auth Required) | `test_indian_job_adapters.py` |
| **Deduplication** | Cross-Source Duplicate Clustering | **Implemented** | `test_duplicate_detection.py` |
| **Job Freshness** | Verification & Lifecycle Tracking | **Implemented** | `test_job_freshness.py` |
| **Relevance & Scoring**| Fast Pre-Filter & Deterministic Scoring | **Implemented** | `test_relevance_engine.py`, `test_matching_engine.py` |
| **Semantic Scoring** | Ollama LLM Semantic Evaluation | **Partially Implemented** | `test_matching_engine.py` (Mocked in unit tests) |
| **Resume Tailoring** | ATS Single-Column PDF & Factual Validation | **Implemented** | `test_resume_tailoring.py`, `test_resume_version_integrity.py` |
| **Approval Workflow** | Cryptographic Approval Fingerprinting | **Implemented** | `test_application_state_machine.py`, `test_application_workflow_service.py` |
| **Synthetic Submission**| Isolated Submission Simulation | **Implemented** | `test_synthetic_submission_workflow.py` |
| **Real External Apply**| Automated External Portal Submission | **Disabled** (Safety Enforced) | `test_synthetic_submission_workflow.py` |
| **Scheduler** | In-Process Asynchronous Pipeline Runner | **Implemented** | `test_scheduler.py` |
| **Notifications** | In-App Alerts, De-duplication, & History | **Implemented** | `test_notifications.py` |
| **Email Digest** | Scheduled Daily/Weekly Job Digests | **Implemented** (Mock/Console/SMTP) | `test_digest_and_delivery_reliability.py` |
| **Web Dashboard** | React 18 + TypeScript + Tailwind UI | **Implemented** | 44 Vitest tests across 12 suites |

---

## 1. Candidate Profile & Master Resume Parsing

### Description & Business Purpose
Allows candidates to upload a master PDF resume to automatically populate their profile (work history, skills, education, and projects). Ensures the candidate maintains a single source of verified truth from which all future job applications are derived.

### Technical Implementation
- **Backend Service**: [`ResumeParserService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/resume_parser.py), [`CandidateService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/candidate_service.py)
- **API Router**: [`backend/app/api/v1/profile.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/profile.py)
- **Database Models**: `CandidateProfile`, `CandidateExperience`, `CandidateEducation`, `CandidateSkill`, `CandidateProject` ([`backend/app/models/candidate.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/candidate.py))
- **Frontend Components**: [`CandidateProfileView.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/profile/CandidateProfileView.tsx), [`ResumeImportModal.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/profile/ResumeImportModal.tsx)
- **API Endpoints**:
  - `GET /api/v1/profile`
  - `PATCH /api/v1/profile`
  - `POST /api/v1/profile/import-resume`
  - `POST /api/v1/profile/import-resume/confirm`
  - `POST/DELETE /api/v1/profile/skills`
  - `POST/DELETE /api/v1/profile/experiences`
  - `POST/DELETE /api/v1/profile/educations`
  - `POST/DELETE /api/v1/profile/projects`
- **Tests**: [`backend/tests/test_candidate_profile.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_candidate_profile.py), [`backend/tests/test_resume_import.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_resume_import.py)
- **Status**: **Implemented**
- **Known Limitations**: PDF parsing uses heuristic regex and section boundary analysis via `pypdf`. Heavily stylized multi-column or image-only scanned PDFs require candidate manual review and confirmation via the confirmation endpoint.

---

## 2. Job Search Preferences & INR LPA Compensation

### Description & Business Purpose
Separates verified candidate career facts (immutable history) from current job search goals (target titles, must-have skills, work mode, and expected compensation). Uses Indian Lakhs Per Annum (INR LPA) as the primary financial model while maintaining backward compatibility with USD.

### Technical Implementation
- **Backend Service**: [`CandidateService.update_search_preferences()`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/candidate_service.py), [`SalaryService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/salary_service.py)
- **API Router**: [`backend/app/api/v1/profile.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/profile.py)
- **Database Model**: `CandidateProfile.search_preferences` (JSON column), `target_package_min_lpa`, `target_package_max_lpa` ([`candidate.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/candidate.py))
- **Frontend Components**: [`SearchPreferencesCard.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/profile/SearchPreferencesCard.tsx)
- **API Endpoints**:
  - `GET /api/v1/profile/preferences`
  - `PUT /api/v1/profile/preferences`
- **Tests**: [`backend/tests/test_search_preferences_persistence_and_salary.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_search_preferences_persistence_and_salary.py), [`frontend/tests/preferences-and-sources.test.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/tests/preferences-and-sources.test.tsx)
- **Status**: **Implemented**
- **Known Limitations**: Currency conversions between INR and foreign currencies use fixed exchange rate formulas (`1 USD ≈ 83 INR`) in `SalaryService` rather than live fluctuating Forex API feeds.

---

## 3. Job Discovery & Multi-Source Collectors

### Description & Business Purpose
Ingests job postings from diverse external platforms, normalizes disparate schemas into a unified structure, and applies instant relevance classification before storage.

### Technical Implementation
- **Backend Pipeline**: [`DiscoveryMatchingPipeline`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/discovery_pipeline.py), [`JobDiscoveryService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/job_discovery_service.py)
- **Adapters**:
  - Greenhouse: [`GreenhouseJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/greenhouse.py)
  - Lever: [`LeverJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/lever.py)
  - Synthetic: [`SyntheticJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/synthetic.py)
  - Naukri: [`NaukriJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/naukri.py)
  - Instahyre: [`InstahyreJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/instahyre.py)
  - Cutshort: [`CutshortJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/cutshort.py)
  - Foundit: [`FounditJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/foundit.py)
  - Hirist: [`HiristJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/hirist.py)
  - Indeed: [`IndeedJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/indeed.py)
  - LinkedIn: [`LinkedInJobAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/linkedin.py)
  - Parser Utilities: [`indian_parser_utils.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/indian_parser_utils.py)
  - Network Security: [`SafeFeedFetcher`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/core/network_security.py)
- **API Router**: [`backend/app/api/v1/jobs.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/jobs.py)
- **Database Models**: `JobSource`, `Job` ([`backend/app/models/job.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/job.py))
- **Frontend Components**: [`DiscoverySourcesCard.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/scheduler/DiscoverySourcesCard.tsx), [`JobDiscoveryModal.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/jobs/JobDiscoveryModal.tsx)
- **API Endpoints**:
  - `GET /api/v1/jobs/sources`
  - `GET /api/v1/jobs/sources/{identifier}`
  - `PUT /api/v1/jobs/sources/{identifier}`
  - `POST /api/v1/jobs/sources/{identifier}/import`
  - `POST /api/v1/jobs/discover`
- **Tests**: [`backend/tests/test_indian_job_discovery_integration.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_discovery_integration.py), [`backend/tests/test_indian_job_adapters.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_adapters.py), [`frontend/tests/IndianJobSources.test.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/tests/IndianJobSources.test.tsx)
- **Status**: **Implemented**
- **Known Limitations**:
  - Automated web scraping is intentionally omitted for Naukri, Instahyre, Cutshort, Foundit, and Indeed due to anti-bot mechanisms.
  - Hirist requires the candidate to provide a valid category RSS/Atom feed URL.

---

## 4. Cross-Source Deduplication & Job Freshness

### Description & Business Purpose
Detects identical job postings listed across multiple sources or re-posted with slight variations, clustering them under a single canonical job to eliminate duplicate work. Tracks job posting activity and verifies active status.

### Technical Implementation
- **Backend Service**: [`DuplicateDetectionService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/duplicate_detection_service.py), [`JobFreshnessService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/job_freshness_service.py)
- **API Router**: [`backend/app/api/v1/jobs.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/jobs.py)
- **Database Models**: `JobDuplicateCluster`, `Job.duplicate_cluster_id`, `Job.freshness_status` ([`job.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/job.py))
- **Frontend Components**: [`DuplicateClustersModal.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/jobs/DuplicateClustersModal.tsx), [`JobsList.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/jobs/JobsList.tsx)
- **API Endpoints**:
  - `GET /api/v1/jobs/duplicates`
  - `POST /api/v1/jobs/duplicates/{cluster_id}/review`
  - `GET /api/v1/jobs/{job_id}/freshness`
  - `POST /api/v1/jobs/{job_id}/freshness/verify`
- **Tests**: [`backend/tests/test_duplicate_detection.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_duplicate_detection.py), [`backend/tests/test_job_freshness.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_job_freshness.py)
- **Status**: **Implemented**
- **Known Limitations**: Similarity scoring combines company name canonicalization, title token overlap, and Jaccard description similarity. Distinct positions with identical titles at the same company apply a `-0.25` penalty if descriptions diverge (<0.20 overlap), preventing false merges.

---

## 5. Job Matching, Relevance & Scoring Engine

### Description & Business Purpose
Evaluates candidate suitability using deterministic rule-based algorithms to produce an explainable, auditable 0–100 match score. Enforces strict eligibility criteria (disqualifying non-compliant roles) and incorporates candidate preference alignment.

### Technical Implementation
- **Backend Services**:
  - Fast Pre-Filter: [`RelevanceEngine`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/relevance_engine.py)
  - Deterministic Scorer: [`DeterministicScoringService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/matching/scoring.py)
  - Eligibility Filter: [`EligibilityService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/matching/eligibility.py)
  - LLM Provider: [`OllamaProvider`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/providers/ollama.py)
- **API Router**: [`backend/app/api/v1/matching.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/matching.py)
- **Database Model**: `MatchScore` ([`backend/app/models/matching.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/matching.py))
- **Frontend Components**: [`JobDetailModal.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/jobs/JobDetailModal.tsx), [`RankingEvaluationModal.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/jobs/RankingEvaluationModal.tsx)
- **API Endpoints**:
  - `POST /api/v1/matching/evaluate/{job_id}`
  - `POST /api/v1/matching/evaluate-all`
  - `GET /api/v1/matching/results`
  - `GET /api/v1/matching/results/{job_id}`
  - `POST /api/v1/matching/evaluate-ranking`
- **Tests**: [`backend/tests/test_matching_engine.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_matching_engine.py), [`backend/tests/test_relevance_engine.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_relevance_engine.py)
- **Status**: **Implemented** (Deterministic Scoring); **Partially Implemented** (Ollama semantic evaluation is optional and falls back gracefully when Ollama is offline).
- **Known Limitations**: Semantic matching requires a locally running Ollama instance (`ollama run llama3.1:latest`). If unavailable, the system transparently relies on 100% deterministic rule-based scoring.

---

## 6. Resume Tailoring, Factual Validation & PDF Generation

### Description & Business Purpose
Tailors the candidate's verified profile to highlight job-relevant skills and experiences. Enforces strict factual grounding to prevent fabricated claims and renders a clean, single-column ATS-friendly PDF with an immutable SHA-256 checksum.

### Technical Implementation
- **Backend Services**:
  - Resume Version Manager: [`ResumeVersionService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/resume_version_service.py)
  - Generator: [`ResumeTailoringService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/resumes/tailoring_service.py)
  - Factual Integrity Checker: [`ResumeFactValidator`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/resumes/fact_validator.py)
  - ReportLab PDF Renderer: [`PdfRenderer`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/resumes/pdf_renderer.py)
- **API Router**: [`backend/app/api/v1/resumes.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/resumes.py)
- **Database Model**: `ResumeVersion` ([`backend/app/models/resume.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/resume.py))
- **Frontend Components**: [`ResumeWorkspace.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/resumes/ResumeWorkspace.tsx)
- **API Endpoints**:
  - `POST /api/v1/resumes/generate`
  - `GET /api/v1/resumes/job/{job_id}`
  - `GET /api/v1/resumes/{version_id}`
  - `GET /api/v1/resumes/{version_id}/download`
  - `GET /api/v1/resumes/{version_id}/integrity`
- **Tests**: [`backend/tests/test_resume_tailoring.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_resume_tailoring.py), [`backend/tests/acceptance/test_resume_version_integrity.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/acceptance/test_resume_version_integrity.py)
- **Status**: **Implemented**
- **Known Limitations**: Only single-column, standard ATS typography is supported by design. Multi-column graphical layouts are intentionally avoided to maximize ATS readability.

---

## 7. Application Workflow & Cryptographic Approvals

### Description & Business Purpose
Manages the application lifecycle through an append-only event state machine. Requires explicit human review and cryptographic SHA-256 approval fingerprinting before any application can proceed toward submission.

### Technical Implementation
- **Backend Workflow**:
  - State Machine: [`ApplicationStateMachine`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/workflow/state_machine.py)
  - Fingerprint Service: [`ApprovalFingerprintService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/workflow/approval_fingerprint.py)
  - Workflow Manager: [`ApplicationWorkflowService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/application_workflow_service.py)
- **API Router**: [`backend/app/api/v1/applications.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/applications.py)
- **Database Models**: `Application`, `ApplicationEvent`, `SubmissionAttempt` ([`backend/app/models/application.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/application.py))
- **Frontend Components**: [`ApplicationQueue.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/applications/ApplicationQueue.tsx), [`ApplicationReviewModal.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/applications/ApplicationReviewModal.tsx), [`ApplicationHistoryDrawer.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/applications/ApplicationHistoryDrawer.tsx), [`OutcomeReconciliationModal.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/applications/OutcomeReconciliationModal.tsx)
- **API Endpoints**:
  - `GET /api/v1/applications`
  - `POST /api/v1/applications/prepare`
  - `GET /api/v1/applications/{application_id}`
  - `GET /api/v1/applications/{application_id}/review`
  - `POST /api/v1/applications/{application_id}/approve`
  - `POST /api/v1/applications/{application_id}/attempt`
  - `GET /api/v1/applications/{application_id}/attempts`
  - `GET /api/v1/applications/{application_id}/events`
  - `POST /api/v1/applications/{application_id}/reconcile`
- **Tests**: [`backend/tests/test_application_state_machine.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_application_state_machine.py), [`backend/tests/test_application_workflow_service.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_application_workflow_service.py), [`backend/tests/test_applications_api.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_applications_api.py)
- **Status**: **Implemented**
- **Known Limitations**: Stale approval detection aborts execution with HTTP 409 if any underlying candidate fact, job requisition text, resume file checksum, or policy version changes between approval and execution.

---

## 8. Synthetic Submission vs. Real External Apply

### Description & Business Purpose
Provides a fully simulated submission workflow for local testing and pipeline validation. Strictly prevents accidental automated application spamming to real external job boards.

### Technical Implementation
- **Synthetic Submission Service**: [`SyntheticSubmissionService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/automation/synthetic_submission_service.py)
- **Synthetic Adapter**: [`SyntheticSubmissionAdapter`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/automation/synthetic_adapter.py)
- **Browser Runner**: [`PlaywrightBrowserRunner`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/automation/browser_runner.py)
- **Local Test Harness**: [`MockPortalServer`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/automation/mock_portal/server.py)
- **Safety Switch**: `settings.JOBPILOT_REAL_SUBMISSION_ENABLED = False` ([`config.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/core/config.py))
- **Tests**: [`backend/tests/test_synthetic_submission_workflow.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_synthetic_submission_workflow.py), [`backend/tests/test_browser_automation.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_browser_automation.py)
- **Status**:
  - **Synthetic Submission**: **Implemented** (`APPROVED` -> `SYNTHETIC_SUBMISSION_IN_PROGRESS` -> `SUBMITTED_SIMULATION`).
  - **Real External Apply**: **Disabled by Design** (`BLOCKED_SAFETY` outcome returned if targeted externally while flag is False).
- **Known Limitations**: Real external submission to live Greenhouse/Lever/Workday career portals is intentionally unmounted and disabled.

---

## 9. Background Scheduler & Automated Pipeline

### Description & Business Purpose
Manages periodic execution of the discovery and matching pipeline in the background without requiring third-party broker dependencies like Celery or Redis.

### Technical Implementation
- **Backend Service**: [`SchedulerService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/scheduler_service.py)
- **API Router**: [`backend/app/api/v1/scheduler.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/scheduler.py)
- **Database Model**: `AutomationRun` ([`backend/app/models/automation.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/automation.py))
- **Frontend Components**: [`SchedulerManager.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/scheduler/SchedulerManager.tsx)
- **API Endpoints**:
  - `GET /api/v1/scheduler/status`
  - `POST /api/v1/scheduler/config`
  - `POST /api/v1/scheduler/run`
  - `GET /api/v1/scheduler/runs`
  - `GET /api/v1/scheduler/runs/{run_id}`
- **Tests**: [`backend/tests/test_scheduler.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_scheduler.py)
- **Status**: **Implemented**
- **Known Limitations**: Runs in-process via Python `asyncio`. Restarting the backend server resets running timers (though configuration is persisted in the database).

---

## 10. Notification Center & Digest Delivery

### Description & Business Purpose
Provides real-time notifications for newly discovered relevant jobs, approval requests, and application lifecycle changes. Generates daily/weekly job digest summaries.

### Technical Implementation
- **Backend Services**: [`NotificationService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/notification_service.py), [`DigestService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/digest_service.py), [`EmailService`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/services/email_service.py)
- **API Router**: [`backend/app/api/v1/notifications.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/api/v1/notifications.py)
- **Database Model**: `Notification` ([`backend/app/models/notification.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/models/notification.py))
- **Frontend Components**: [`NotificationCenter.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/notifications/NotificationCenter.tsx), [`NotificationSettingsModal.tsx`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/frontend/src/features/notifications/NotificationSettingsModal.tsx)
- **API Endpoints**:
  - `GET /api/v1/notifications`
  - `GET /api/v1/notifications/unread-count`
  - `POST /api/v1/notifications/{id}/read`
  - `POST /api/v1/notifications/read-all`
  - `POST /api/v1/notifications/{id}/dismiss`
  - `GET /api/v1/notifications/preferences`
  - `PUT /api/v1/notifications/preferences`
  - `GET /api/v1/notifications/digest/status`
  - `POST /api/v1/notifications/digest/trigger`
  - `GET /api/v1/notifications/delivery-history`
  - `POST /api/v1/notifications/test-email`
  - `GET /api/v1/notifications/email-status`
- **Tests**: [`backend/tests/test_notifications.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_notifications.py), [`backend/tests/test_digest_and_delivery_reliability.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_digest_and_delivery_reliability.py)
- **Status**: **Implemented**
- **Known Limitations**: Email delivery default provider is `"mock"`. Real SMTP delivery requires valid SMTP credentials in `.env`.

---

*Reference Document*: Proceed to [02_TECHNICAL_ARCHITECTURE.md](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/docs/project-reference/02_TECHNICAL_ARCHITECTURE.md) for technical design, data flows, and component architecture.
