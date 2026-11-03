# 11 — Git History & Milestone Release Notes

## 1. Verified Repository Branches

As verified via `git branch -a` on November 3, 2026:

| Branch Name | Tracking Remote | Role / Purpose |
| :--- | :--- | :--- |
| **`feature/stop-working-for-now-in-job-pilot`** *(ACTIVE)* | `origin/feature/stop-working-for-now-in-job-pilot` | **Active Reference Branch**: Created to pause development cleanly, containing all merged Phase 1–12 work, Indian job board integrations, and security hardening. |
| **`main`** | `origin/main` | Production branch containing merged releases up to Pull Request #2 (`7f89fa7`). |
| **`feature/indian-job-board-integrations`** | `origin/feature/indian-job-board-integrations` | Feature branch for Indian job board integrations (Naukri, Instahyre, Cutshort, Hirist, Foundit, LinkedIn, Indeed), SSRF socket validation, and savepoint isolation. Merged into main via PR #2. |
| **`feature/job-discovery-relevance-and-preferences`** | `origin/feature/job-discovery-relevance-and-preferences` | Feature branch for career relevance upgrades, INR LPA salary preferences, and discovery filtering. Merged into main via PR #1 (`6cc1bfa`). |
| **`feature/job-alert-email-integration`** | `origin/feature/job-alert-email-integration` | Feature branch for email alerts and digest integrations. |

---

## 2. Milestone Commit History & Chronology

```
7f89fa7 (HEAD -> feature/stop-working-for-now-in-job-pilot, main) Merge PR #2: feature/indian-job-board-integrations
  │
  ├─ 76669fb feat: add compliant Indian job source integrations
  │
6cc1bfa Merge PR #1: feature/job-discovery-relevance-and-preferences
  │
  ├─ 7711bb0 feat: upgrade job discovery relevance and INR salary preferences
  │
8eba9fe feat: prepare repository for publication with comprehensive documentation and pipeline hardening
ebd261e feat(phase-12): production readiness, live-source hardening, regression suite, and e2e workflow
7534c4a feat(matching): Phase 11 - Job-matching quality, cross-source deduplication, freshness, user feedback, offline evaluation
ee21ba2 feat(notifications): complete Phase 10 - notification delivery reliability and digest scheduling
6b7d7ae feat(preferences): complete Phase 9 - personalized job search, source management, and smart alerts
295571a feat(validation): complete Phase 8 - end-to-end validation and reliability hardening
d2f2dfb feat(scheduler): complete Phase 7 - scheduled discovery, matching pipeline, and persistent notifications
e0feb8e feat(frontend): complete Phase 6 - production React TypeScript dashboard with live API integration and test suite
88609e5 feat(application): complete Phase 5 Step 5 - Application Workflow API router, schemas, and integration tests
c0902b6 feat(automation): complete Phase 5 Step 4 - Playwright automation adapter, conservative form mapper, mock portal harness
6cb72af feat(workflow): implement application workflow service, review payload, and canonical approval fingerprinting
```

---

## 3. Milestone Release Summaries

### Milestone: Indian Job Board Integrations (PR #2, Commit `76669fb` & `7f89fa7`)
- **Key Deliverables**:
  - Integrated 7 Indian job platforms: Naukri, Instahyre, Cutshort, Hirist, Foundit, LinkedIn, Indeed.
  - Implemented `SafeFeedFetcher` and `SSRFSafeNetworkBackend(AnyIOBackend)` to defeat DNS rebinding (TOCTOU) by validating socket peer IPs immediately upon TCP connection.
  - Implemented `safe_parse_xml()` to prohibit `<!DOCTYPE` and `<!ENTITY>` definitions, preventing XXE in RSS parsing.
  - Added savepoint isolation (`session.begin_nested()`) in discovery loops to prevent single malformed records from invalidating entire batch imports.
  - Calibrated `DuplicateDetectionService.compute_similarity()` with a `-0.25` penalty for divergent descriptions (<0.20 overlap), preventing false merges.
  - Alembic migration `d823fa19b2e4` added `source_type` and `integration_status` to `job_sources`.
  - Pytest suite expanded to 247 tests (100% passing).

### Milestone: Job Discovery Relevance & INR Salary Preferences (PR #1, Commit `7711bb0` & `6cc1bfa`)
- **Key Deliverables**:
  - Replaced legacy USD-centric compensation system with India-focused **Expected Package in INR Lakhs Per Annum (LPA)**.
  - Built `RelevanceEngine` deterministic fast pre-filter, preventing irrelevant jobs from triggering deep resume generation.
  - Fixed preference persistence issues across save/reload cycles in `SearchPreferencesCard`.
  - Alembic migration `c14fd127ea45` added `target_package_min_lpa` and `target_package_max_lpa` to `candidate_profiles`.

### Milestone: Phase 12 Production Readiness & E2E Hardening (Commit `ebd261e`)
- **Key Deliverables**:
  - Comprehensive 12-stage end-to-end test in `test_production_readiness_e2e.py`.
  - Live source error isolation for Greenhouse and Lever adapters.
  - Alembic migration `e145f6789abc` indexed `canonical_url` and `discovered_at` for high-throughput queries.

### Milestone: Phase 11 Job Intelligence & Deduplication (Commit `7534c4a`)
- **Key Deliverables**:
  - Built `DuplicateDetectionService` for cross-board deduplication with canonical job clustering.
  - Built `JobFreshnessService` for tracking active/stale/expired job postings.
  - Added candidate recommendation feedback (thumbs up/down) in `job_feedbacks` table.
  - Built `OfflineEvaluator` running Normalized Discounted Cumulative Gain (nDCG@K) benchmarks.

### Milestone: Phase 10 Notification Delivery & Digest Scheduling (Commit `ee21ba2`)
- **Key Deliverables**:
  - Built in-app notification center with deduplication keys (`dedup_key`).
  - Added `DigestService` generating daily and weekly candidate digests.
  - Implemented pluggable `EmailService` supporting `"mock"`, `"console"`, and `"smtp"` delivery.

### Milestone: Phase 9 Search Preferences & Personalization (Commit `6b7d7ae`)
- **Key Deliverables**:
  - Strict partitioning of verified candidate facts from mutable search preferences.
  - Added `DiscoverySourcesCard` in frontend for toggling job boards.

### Milestone: Phase 6 Production React Frontend (Commit `e0feb8e`)
- **Key Deliverables**:
  - Built full React 18 + TypeScript + Tailwind CSS web dashboard.
  - Implemented 44 Vitest tests covering all major UI screens and modals.

### Milestone: Phase 5 Application Workflow & Approval Security (Commit `88609e5` to `6cb72af`)
- **Key Deliverables**:
  - Built finite state machine in `ApplicationStateMachine`.
  - Implemented cryptographic SHA-256 `ApprovalFingerprintService` to eliminate stale approvals.
  - Built local synthetic submission harness (`SyntheticSubmissionService` + `MockPortalServer`).
  - Enforced `JOBPILOT_REAL_SUBMISSION_ENABLED = False` safety switch.

---

*Reference Document*: Proceed to [12_FUTURE_RESUME_GUIDE.md](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/docs/project-reference/12_FUTURE_RESUME_GUIDE.md) for step-by-step instructions on resuming development after a long break.

