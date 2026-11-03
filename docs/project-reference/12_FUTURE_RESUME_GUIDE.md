# 12 — Future Resume Guide: Resuming Development After a Hiatus

> [!IMPORTANT]
> **Read this guide first** when returning to JobPilot AI after months or years away from the codebase. It provides an immediate mental map, validation checklist, and safe resumption instructions.

---

## 1. What the Project Does (In 30 Seconds)

**JobPilot AI** is a personal, local-first AI job-hunting agent and application management platform. It:
1. Extracts verified candidate facts from an uploaded master PDF resume.
2. Discovers matching jobs from Greenhouse, Lever, Hirist RSS, and manual imports (Naukri, Instahyre, Cutshort, Foundit, Indeed, LinkedIn).
3. Evaluates listings using deterministic scoring rules and candidate search preferences (target titles, skills, and **INR LPA** compensation).
4. Detects cross-board duplicate postings and clusters them into single canonical records.
5. Generates fact-grounded, single-column ATS resume PDFs with zero AI hallucination (enforced by `ResumeFactValidator`).
6. Enforces human-in-the-loop review with a cryptographic SHA-256 approval fingerprint before any application can proceed.
7. Executes submissions in an isolated **Local Synthetic Mode** without spamming external job boards (`JOBPILOT_REAL_SUBMISSION_ENABLED=False`).

---

## 2. What Was Completed vs. What Was Not Completed

### What Was Completed (100% Operational)
- Master resume PDF ingestion and profile management.
- Job search preferences with INR LPA package expectations.
- Job discovery across Greenhouse, Lever, Hirist RSS, and 5 manual import adapters.
- SSRF and DNS rebinding protection via socket-level peer IP interception (`SSRFSafeNetworkBackend`).
- Safe XML parsing (`safe_parse_xml`) preventing XXE.
- Cross-source duplicate detection with Jaccard description calibration.
- Deterministic 0–100 matching engine and hard eligibility gates.
- Fact-grounded resume tailoring and ReportLab ATS PDF generation with SHA-256 checksums.
- Finite state machine with append-only event auditing.
- Cryptographic approval fingerprinting preventing stale approvals.
- Isolated synthetic submission simulation harness.
- In-process background scheduler for periodic discovery.
- In-app notification center and daily/weekly job digests.
- Full React 18 + TypeScript + Tailwind CSS web dashboard.
- 247/247 backend tests passing, 44/44 frontend tests passing, clean production build.
- Single linear Alembic migration head `d823fa19b2e4`.

### What Was Not Completed (Intentional Boundaries & Future Backlog)
- **Live external automated submission**: Disabled by design for safety.
- **Automated headless scraping for Naukri/Cutshort/Instahyre**: Intentionally manual due to Cloudflare anti-bot mechanisms.
- **Browser extension for one-click job importing**: Documented as Phase 13 in roadmap.
- **Human-supervised Playwright form-filler copilot**: Documented as Phase 14 in roadmap.
- **Prometheus `/metrics` telemetry**: Documented as Phase 15 in roadmap.

---

## 3. Current Git & Repository State

- **Active Development Branch**: `feature/stop-working-for-now-in-job-pilot`
- **Latest Merged Commit on Main**: `7f89fa7` (*Merge pull request #2 from akash-thakur09/feature/indian-job-board-integrations*)
- **Working Tree**: Clean (`git status` reports working tree clean, `git diff --check` reports 0 errors).
- **Default Database**: SQLite local storage at `storage/jobpilot.db`.

---

## 4. How to Set Up & Verify the Project Again

### Step 1: Environment Setup
```powershell
# Navigate to repository root
cd job_finder

# Ensure virtual environment exists and is activated
.\backend\.venv\Scripts\Activate.ps1

# Verify installed Python packages
pip install -r backend\requirements.txt

# Verify Node dependencies
cd frontend
npm install
cd ..
```

### Step 2: Database Migration Check
```powershell
# Check current migration head
.\backend\.venv\Scripts\alembic.exe -c backend/alembic.ini current
# Must output: d823fa19b2e4 (head)

# If database is missing, run:
.\backend\.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade head
```

### Step 3: Run Full Verification Tests
```powershell
# 1. Run all backend tests (expect 247 passed)
.\backend\.venv\Scripts\pytest.exe backend/tests/ -v

# 2. Run all frontend tests (expect 44 passed across 12 files)
cd frontend
npx vitest run

# 3. Test frontend production build
npm run build
cd ..

# 4. Check git whitespace cleanliness
git diff --check
```

### Step 4: Run the Application Locally
Open two terminal windows:
```powershell
# Terminal 1: Backend API (Uvicorn)
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend UI (Vite)
cd frontend
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## 5. Which Features Should Be Checked First Upon Resuming

When you first open the web dashboard:
1. **Candidate Profile (`/profile`)**:
   - Check that candidate name, contact details, experiences, and skills render properly.
   - Verify that **Search Preferences** shows expected package in **INR LPA** (e.g., 20 LPA).
2. **Discovery Sources (`/scheduler`)**:
   - Verify that the 10 job sources appear in `DiscoverySourcesCard`.
   - Check that Greenhouse and Lever show `ACTIVE_POLLING`, Hirist shows `CONFIGURATION_REQUIRED`, and Naukri/Instahyre/Cutshort show `MANUAL_IMPORT_ONLY`.
3. **Jobs List (`/jobs`)**:
   - Verify that job cards display deterministic eligibility badges, relevance scores, and duplicate badges.
4. **Resume Workspace (`/resumes`)**:
   - Verify tailored resume PDF rendering and click **Verify Integrity** to confirm the SHA-256 matches.
5. **Application Queue (`/applications`)**:
   - Verify application status tabs (`Ready for Review`, `Approved`, `Simulation`).
   - Open review modal, approve an application, and click **Execute Synthetic Run** to confirm simulation transitions to `SUBMITTED_SIMULATION`.

---

## 6. Recommended Next Development Task

When ready to write code again, implement **Phase 13: Browser Extension Ingestion** (from [10_FUTURE_ROADMAP_AND_BACKLOG.md](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/docs/project-reference/10_FUTURE_ROADMAP_AND_BACKLOG.md)):
- **Goal**: Create a lightweight Manifest V3 Chrome extension that captures active job listings from Naukri or LinkedIn tabs and posts structured JSON to `http://127.0.0.1:8000/api/v1/jobs/sources/{id}/import`.
- **Why this first?**: It directly solves the manual copy-pasting friction for Indian job boards without modifying core backend or database schemas.

---

## 7. Safe Git Workflow for Future Development

Always adhere to this branch and commit discipline:
1. **Never commit directly to `main`**:
   ```powershell
   git checkout main
   git pull origin main
   git checkout -b feature/<descriptive-feature-name>
   ```
2. **Run the quality suite before committing**:
   ```powershell
   .\backend\.venv\Scripts\pytest.exe backend/tests/
   cd frontend; npx vitest run; npm run build; cd ..
   git diff --check
   ```
3. **Keep migrations linear**:
   - Never manually edit existing migration files in `backend/alembic/versions/`.
   - Always generate new migrations extending `d823fa19b2e4` with `alembic revision -m "..."`.
4. **Preserve Safety Flags**:
   - Never set `JOBPILOT_REAL_SUBMISSION_ENABLED = True` in version control.
   - Keep `JOBPILOT_SYNTHETIC_DISCOVERY_ENABLED = False` by default.

---

## 8. AI Coding-Agent Resumption Prompt

When delegating future work on JobPilot AI to an AI coding assistant, copy and paste this exact prompt into the prompt box:

```text
You are working on the existing JobPilot AI codebase (repository: job_finder).

Before making any changes or proposing architectural refactors:

1. Read the complete documentation suite inside `docs/project-reference/`, starting with `00_PROJECT_OVERVIEW.md`, `01_FEATURES_AND_IMPLEMENTATION_STATUS.md`, and `02_TECHNICAL_ARCHITECTURE.md`.
2. Inspect the actual repository state: check the active git branch (`git branch`), latest commit (`git log -n 5`), Alembic migration head (`alembic current`), and run the existing test suite (`pytest backend/tests/` and `cd frontend; npx vitest run`).
3. Do NOT immediately modify code, create migrations, or install new dependencies.
4. Identify any discrepancies between the documentation and the live repository.
5. Ensure safety switches remain strictly enforced (`JOBPILOT_REAL_SUBMISSION_ENABLED=False`, `JOBPILOT_SYNTHETIC_DISCOVERY_ENABLED=False`).
6. Propose the smallest safe, incremental step aligned with the project roadmap in `docs/project-reference/10_FUTURE_ROADMAP_AND_BACKLOG.md`.
7. Preserve the original JobPilot AI local-first, privacy-focused, human-governed scope.
```

---

*Documentation Suite Complete*: You have finished the JobPilot AI Project Knowledge & Handover Reference.
