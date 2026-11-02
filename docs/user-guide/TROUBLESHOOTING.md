# JobPilot AI — Troubleshooting & Diagnostic Guide

This guide provides practical diagnostic procedures and solutions for common operational issues, error messages, and edge cases across JobPilot AI.

---

## Diagnostic Quick Reference Table

| Symptom / Error Message | Probable Root Cause | Quick Fix Command / Action | Section |
| :--- | :--- | :--- | :--- |
| **`[WinError 10048] address already in use`** | Port `8000` or `5173` occupied by orphan process | `Get-Process python \| Stop-Process -Force` | [Issue 1 & 2](#1-backend--frontend-startup-failures) |
| **`ModuleNotFoundError: No module named 'fastapi'`** | System Python invoked instead of `.venv` | Run `python run.py` (auto-delegates to `.venv`) | [Issue 1](#1-backend--frontend-startup-failures) |
| **`sqlite3.OperationalError: database is locked`** | Concurrent write or dangling SQLite connection | Stop background processes; restart backend | [Issue 3](#3-database-locks-and-alembic-migration-errors) |
| **`alembic.util.exc.CommandError: Can't locate revision`** | Unmigrated SQLite DB after git branch switch | Run `python -m alembic upgrade head` | [Issue 3](#3-database-locks-and-alembic-migration-errors) |
| **`HTTP 500 Internal Server Error`** | Unhandled exception in backend route handler | Check backend terminal logs for traceback | [Issue 4](#4-http-500-internal-server-errors) |
| **`httpx.ReadTimeout` on Greenhouse** | Company board has large job catalog (>300 jobs) | Timeout increased to 25.0s in adapter | [Issue 5](#5-greenhouse--lever-adapter-network-failures) |
| **`Board token 'xyz' not found (404)`** | Invalid or deprecated ATS board slug | Verify token in public ATS URL | [Issue 5](#5-greenhouse--lever-adapter-network-failures) |
| **Discovery returns 0 jobs** | Source board has 0 active postings or wrong slug | Verify board on `boards.greenhouse.io/{slug}` | [Issue 6](#6-discovery-returns-0-jobs-or-fails-mid-run) |
| **Eligible job unexpectedly marked `DISQUALIFIED`** | Candidate work auth or remote preference mismatch | Check failed rules in Job Detail Modal | [Issue 7](#7-unexpected-job-disqualification) |
| **Match score seems unexpectedly low (<60%)** | Missing verified skills or unaligned salary threshold | Verify required skills on candidate profile | [Issue 8](#8-unexpected-scoring-or-ranking-behavior) |
| **Duplicate jobs appear in feed** | Job title/company similarity below 0.85 threshold | Open Duplicates modal and link manually | [Issue 9](#9-duplicate-jobs-appearing-in-feed) |
| **`FactualValidationReport: Unsupported claims found`** | Resume tailoring attempted to claim unverified skill | Add missing skill to candidate profile facts | [Issue 10](#10-resume-tailoring--fact-validation-failures) |
| **`is_ats_valid: False` on PDF** | Non-standard heading or margin overflow | Ensure standard headings; check PDF verifier | [Issue 11](#11-ats-pdf-verification-failures) |
| **`ResumeIntegrityError: SHA-256 mismatch`** | PDF on disk was modified after generation | Re-tailor resume to create a new clean version | [Issue 12](#12-sha-256-checksum-integrity-failures) |
| **`ApplicationNotReviewableError`** | Job is disqualified or missing resume version | Ensure job is eligible before preparing | [Issue 13](#13-application-preparation-conflicts) |
| **`ApprovalFingerprintMismatchError: Data drift`** | Profile or job facts modified after approval | Re-review application and re-approve | [Issue 14](#14-approval-fingerprint-mismatch--data-drift) |
| **Notification unread count stuck** | Read state desynchronized in local browser cache | Click "Mark All Read" in Notification drawer | [Issue 15](#15-notification-center-desynchronization) |
| **`SMTPAuthenticationError` or Connection Refused** | Incorrect SMTP credentials or disabled app password | Generate App Password; test in settings modal | [Issue 16](#16-email-and-smtp-delivery-failures) |
| **Scheduler jobs trigger multiple times** | Multiple Uvicorn worker processes running | Run single worker (`python run.py`) | [Issue 17](#17-apscheduler-timing-or-concurrency-issues) |
| **Ollama connection timeout / offline** | Ollama daemon not running on port 11434 | Run `ollama serve` or let fallback engine run | [Issue 18](#18-ollama-local-llm-unreachable) |

---

## 1. Backend & Frontend Startup Failures

### Symptom: `[WinError 10048] Only one usage of each socket address is normally permitted` (Port 8000 or 5173 occupied)
- **Root Cause**: A previous backend or frontend process was terminated abruptly and remains running in the background.
- **Diagnostic Command**:
  ```powershell
  # Check which process is holding port 8000
  Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object OwningProcess
  ```
- **Remediation**:
  ```powershell
  # Kill process occupying port 8000 (replace <PID> with process ID)
  Stop-Process -Id <PID> -Force

  # Or kill all dangling Python/Uvicorn processes
  Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
  ```

### Symptom: `ModuleNotFoundError: No module named 'fastapi'`
- **Root Cause**: Running `python backend/app/main.py` using system Python rather than the virtual environment.
- **Remediation**:
  Always start the backend via the root launcher, which auto-delegates to the virtualenv:
  ```powershell
  python run.py
  ```
  Or explicitly invoke the virtualenv interpreter:
  ```powershell
  .\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
  ```

---

## 2. Frontend Build and Runtime Failures

### Symptom: `Failed to resolve import "lucide-react"` or `vite: command not found`
- **Root Cause**: Frontend dependencies have not been installed.
- **Remediation**:
  ```powershell
  cd frontend
  npm install
  npm run build
  ```

---

## 3. Database Locks and Alembic Migration Errors

### Symptom: `sqlite3.OperationalError: database is locked`
- **Root Cause**: SQLite allows multiple concurrent readers, but only one writer. If a long discovery run or parallel test process holds an open write transaction, subsequent writes fail.
- **Remediation**:
  1. Terminate any parallel test runs or dangling background tasks.
  2. Restart the backend process (`python run.py`).
  3. Ensure SQLite database file is on a local SSD drive (not a network share or synced OneDrive folder).

### Symptom: `alembic.util.exc.CommandError: Can't locate revision identified by 'e145f6789abc'`
- **Root Cause**: The local SQLite database schema was stamped with a migration revision from another branch.
- **Remediation**:
  ```powershell
  # Verify current migration status
  python -m alembic current

  # Apply all migrations to head
  python -m alembic upgrade head
  ```

---

## 4. HTTP 500 Internal Server Errors

### Diagnostic Procedure
1. Observe the exact backend terminal output where `python run.py` is running.
2. FastAPI outputs full Python tracebacks to the console in development mode.
3. Common culprit: Passing an un-awaited coroutine or accessing lazy-loaded SQLAlchemy relationships outside of an `AsyncSession` context. Look for `MissingGreenlet` errors.
4. Ensure all database relationships are loaded eagerly via `.options(selectinload(...))` or `.options(joinedload(...))`.

---

## 5. Greenhouse & Lever Adapter Network Failures

### Symptom: `httpx.ReadTimeout` during Greenhouse Discovery
- **Root Cause**: Certain large company boards (e.g. Canonical with 300+ postings) return extensive HTML payloads that take over 10 seconds to download on slower connections.
- **Remediation**:
  The default timeout in `backend/app/collectors/greenhouse.py` and `lever.py` is configured to `25.0` seconds. If your connection is exceptionally slow, increase `timeout_seconds`:
  ```python
  class GreenhouseJobAdapter(BaseJobAdapter):
      def __init__(self, timeout_seconds: float = 35.0):
          ...
  ```

### Symptom: `Board token 'xyz' returned HTTP 404`
- **Root Cause**: The board identifier is incorrect or the company has moved to a private ATS.
- **Verification**:
  Open `https://boards.greenhouse.io/{token}` or `https://jobs.lever.co/{token}` in your browser. If it returns 404, the slug is invalid.

---

## 6. Discovery Returns 0 Jobs or Fails Mid-Run

### Diagnostic Steps
1. Navigate to `/scheduler` and inspect the **Automation Run History** table.
2. Click the failed run to read the execution log.
3. If `jobs_fetched: 0`, verify that the company currently has public postings listed on their website.
4. If the run status is `PARTIAL_FAILURE`, check which specific adapter encountered network drops. The pipeline automatically isolates failures so successful adapters still save their jobs.

---

## 7. Unexpected Job Disqualification

### Symptom: A job you want to apply to shows red `DISQUALIFIED` badge
- **Root Cause**: A hard deterministic constraint failed.
- **Diagnostic Procedure**:
  1. Click the job card to open **Job Detail Modal**.
  2. Inspect the **Eligibility Criteria** alert box.
  3. Common causes:
     - **Company Exclusions**: The company name matches an entry in your **Excluded Companies** preference. Remove the company name in `/profile` under Preferences tab.
     - **Work Authorization**: The job requires `"US Citizenship"` or `"Active Security Clearance"`, but candidate profile states `REQUIRES_SPONSORSHIP` or `UK_CITIZEN`.
     - **Remote Preference**: The candidate selected `REMOTE_ONLY`, but the job is classified as `ONSITE` in a different city.

---

## 8. Unexpected Scoring or Ranking Behavior

### Symptom: Overall match score is lower than expected (e.g. 52% for a role you fit well)
- **Root Cause**: Missing verified skills on your candidate profile.
- **Explanation**:
  Policy 1.1.0 gives a **35% weight** to technical skills match. The scoring engine only credits skills that are:
  1. Extracted from the job description, AND
  2. Present in the candidate's verified skills list (`is_verified == True`).
- **Remediation**:
  1. Open Job Detail Modal and check the **Missing Skills** list.
  2. If you possess those skills, navigate to `/profile` and add them under **Verified Skills**.
  3. Return to the job and click **Evaluate Job**. The score will recalculate immediately.

---

## 9. Duplicate Jobs Appearing in Feed

### Symptom: Two identical job postings appear as separate entries
- **Root Cause**: Title or company string variation fell below the default 0.85 deduplication similarity threshold (e.g. "Software Engineer II" vs "Senior Software Developer").
- **Remediation**:
  1. Click **Duplicates** button on `/jobs`.
  2. If the jobs appear in a cluster, confirm the canonical record.
  3. If unclustered, trigger manual deduplication via `POST /api/jobs/deduplicate`.

---

## 10. Resume Tailoring & Fact Validation Failures

### Symptom: `FactualValidationReport: Unsupported claims found: Skill 'Kubernetes' is not a verified candidate skill.`
- **Root Cause**: The resume tailoring prompt or algorithm attempted to insert a skill into the tailored resume that does not exist in your verified profile.
- **Safety Invariant**: JobPilot AI **strictly refuses** to generate resumes containing unverified candidate claims.
- **Remediation**:
  If you have experience with the skill:
  1. Go to `/profile`.
  2. Add the skill under **Verified Skills** with your years of experience.
  3. Re-run **Tailor Resume**. The validator will pass.

---

## 11. ATS PDF Verification Failures

### Symptom: `is_ats_valid: False` on tailored resume
- **Root Cause**: The generated PDF failed one of the automated layout audit checks in `ResumePdfVerifier`.
- **Diagnostic Checklist**:
  - Missing standard section headings (`SUMMARY`, `SKILLS`, `EXPERIENCE`, `EDUCATION`).
  - Text extraction produced empty or corrupted unicode strings.
  - Text bounds exceeded standard margins.
- **Remediation**:
  Ensure candidate profile contains standard employment dates and company names. Note: If candidate has no formal education records, `ResumePdfVerifier` allows omitting the `EDUCATION` heading.

---

## 12. SHA-256 Checksum Integrity Failures

### Symptom: `ResumeIntegrityError: Stored hash does not match binary on disk`
- **Root Cause**: The PDF file located in `storage/resumes/{id}.pdf` was edited, overwritten, or corrupted by an external program.
- **Remediation**:
  Never manually edit PDF files in `storage/resumes/`. To generate a corrected resume:
  1. Open the job in JobPilot AI.
  2. Click **Tailor Resume** to compile a fresh, cryptographically hashed version.

---

## 13. Application Preparation Conflicts

### Symptom: `HTTP 400: Cannot prepare application for disqualified job`
- **Root Cause**: Attempted to prepare an application for a job that failed hard eligibility rules.
- **Remediation**:
  Review job requirements in Job Detail Modal. If your profile facts were incorrect (e.g. work authorization updated), update profile facts, re-evaluate the job, and then prepare the application.

---

## 14. Approval Fingerprint Mismatch & Data Drift

### Symptom: Approved application suddenly reverts to `READY_FOR_REVIEW`
- **Root Cause**: The system's drift monitor detected that underlying facts changed after you approved the application.
- **Explanation**:
  If you edit your candidate name, email, or verified skills, or if the job description changed, the approval fingerprint becomes invalid. JobPilot AI invalidates the approval to ensure you never submit out-of-date or unverified documents.
- **Remediation**:
  1. Open the Application Queue at `/applications`.
  2. Click **Review Application**.
  3. Inspect the updated data.
  4. Click **Approve Application** to generate a new valid approval fingerprint.

---

## 15. Notification Center Desynchronization

### Symptom: Notification badge shows unread alerts, but drawer appears empty
- **Remediation**:
  1. Open the drawer by clicking the bell icon.
  2. Click **Mark All Read**.
  3. Refresh the browser page (`F5`).

---

## 16. Email and SMTP Delivery Failures

### Symptom: `SMTPAuthenticationError: (535, '5.7.8 Username and Password not accepted')`
- **Root Cause**: Modern email providers (e.g. Gmail) do not allow account passwords for automated SMTP scripts.
- **Remediation**:
  1. Enable 2-Step Verification on your email account.
  2. Generate an **App Password** (16 characters) specifically for JobPilot AI.
  3. Enter the App Password in the Notification Settings modal in JobPilot AI.
  4. Click **Send Test Email** to confirm.

---

## 17. APScheduler Timing or Concurrency Issues

### Symptom: Scheduled discovery runs trigger twice at the same minute
- **Root Cause**: Running multiple Uvicorn worker processes (e.g. `uvicorn --workers 2`). Each worker runs its own internal APScheduler instance.
- **Remediation**:
  Always run the backend with a single worker process:
  ```powershell
  python run.py
  ```

---

## 18. Ollama Local LLM Unreachable

### Symptom: Resume tailoring takes longer than usual or logs Ollama connection warnings
- **Root Cause**: Ollama is not installed or not running on `http://localhost:11434`.
- **System Behavior**:
  JobPilot AI features a **deterministic fallback tailoring engine**. If Ollama is offline, the system automatically uses deterministic rule-based keyword matching and section re-ranking. Resume generation will succeed even without Ollama.
- **Remediation (To enable LLM enhancement)**:
  ```powershell
  # Start Ollama service in a separate terminal
  ollama serve

  # Verify model is available
  ollama list
  # Pull model if missing
  ollama pull llama3.1:latest
  ```

