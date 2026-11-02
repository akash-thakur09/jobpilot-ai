# JobPilot AI — Daily Job-Search Checklist

This checklist provides a quick-reference operational guide for using JobPilot AI in your daily job search. Keep this document handy for your morning routine and weekly pipeline audits.

---

## Phase 1: Initial Setup Checklist (One-Time)

Complete these steps before running your first discovery cycle:

- [ ] **System Verification**:
  - [ ] Backend running on `http://127.0.0.1:8000/` (`python run.py`).
  - [ ] Frontend running on `http://localhost:5173/` (`npm run dev`).
  - [ ] Database migrations applied (`python -m alembic upgrade head`).
- [ ] **Candidate Facts (Immutable)**:
  - [ ] Legal full name, email, and phone number verified on `/profile`.
  - [ ] Legal work authorization set accurately (`US_CITIZEN`, `GREEN_CARD`, `UK_CITIZEN`, `REQUIRES_SPONSORSHIP`).
  - [ ] Master resume imported and parsed.
  - [ ] At least 8–15 core technical skills verified with accurate years of experience.
  - [ ] All previous employer names, titles, and dates checked for accuracy.
- [ ] **Search Preferences (Volatile)**:
  - [ ] Target job titles entered (comma-separated).
  - [ ] Remote preference configured (`REMOTE`, `HYBRID`, or `ALL`).
  - [ ] Target location entered.
  - [ ] Minimum desired salary threshold set.
  - [ ] Excluded company blacklist populated (e.g. current employer).
- [ ] **Discovery Sources**:
  - [ ] At least 2–3 target employer boards added under `/scheduler` (e.g. `canonical`, `gitlab`, `leverdemo`).
  - [ ] Source adapters toggled to **Enabled**.
- [ ] **Notification Channel**:
  - [ ] In-app notification bell checked.
  - [ ] (Optional) SMTP credentials tested and verified in Settings modal.

---

## Phase 2: Daily Morning Routine (10–15 Minutes)

Run this routine every weekday morning:

### 1. Ingestion & Digest Review (3 Minutes)
- [ ] Open JobPilot AI at `http://localhost:5173/`.
- [ ] Click the **Notification Bell** icon in the TopBar.
- [ ] Read the morning digest summary. Note how many new jobs were discovered.
- [ ] If background discovery was paused, click **Discover Jobs** $\to$ **All Active Sources** on `/jobs` to run an on-demand sweep.

### 2. Job Feed & Triage (5 Minutes)
- [ ] Navigate to `/jobs`.
- [ ] Filter by **Eligibility: Eligible**.
- [ ] Sort/inspect jobs with **Match Score $\ge 75\%$**.
- [ ] Click on high-match cards to inspect the **Job Detail Modal**:
  - [ ] Review **Matched Skills** vs **Missing Skills**.
  - [ ] Check compensation range against expectations.
  - [ ] Verify role freshness (prefer postings $< 14$ days old).
- [ ] If a job looks relevant, click **Tailor Resume**.
- [ ] If a role is not a good fit, click **Feedback: Irrelevant** to tune the ranking model.

### 3. Tailored Resume & Application Preparation (4 Minutes)
- [ ] Navigate to `/resumes`.
- [ ] Select the newly tailored resume version.
- [ ] Check the **ATS Compliance Checklist**:
  - [ ] Single-column layout: Passed.
  - [ ] Standard headings: Passed.
  - [ ] Clean text extractability: Passed.
- [ ] Click **Download PDF** to save a local copy of the tailored resume.
- [ ] Return to the job or queue and click **Prepare Application**.

### 4. Human Approval & Manual Submission (3 Minutes)
- [ ] Navigate to `/applications`.
- [ ] Open the **Ready for Review** tab.
- [ ] Click **Review Application** on the prepared packet.
- [ ] Verify the target employer, attached resume version, and form answers.
- [ ] Click **Approve Application** (generates immutable SHA-256 approval fingerprint).
- [ ] Click the **External Job URL** link to open the official employer career page.
- [ ] Fill out the employer's application form, attach your downloaded tailored PDF, and submit.
- [ ] Return to JobPilot AI and click **Mark as Submitted**.

---

## Phase 3: Weekly Pipeline Review (20–30 Minutes)

Run this routine every Friday or Monday morning:

### 1. Active Application Triage
- [ ] Navigate to `/applications`.
- [ ] Review applications in **Submitted** state:
  - [ ] Check application dates (follow up on applications older than 10 business days).
  - [ ] For any responses received via email, click **Update Outcome**:
    - [ ] `INTERVIEW`: Log interview stage and date.
    - [ ] `REJECTED`: Log rejection feedback.
    - [ ] `OFFER`: Record offer compensation details.

### 2. Board Health & Source Maintenance
- [ ] Navigate to `/scheduler`.
- [ ] Inspect the **Automation Run History** table.
- [ ] Look for any sources with `ERROR` status.
- [ ] If a board token returns 404, check if the company updated their career board URL.
- [ ] Add 2–3 new target company boards to maintain fresh job discovery volume.

### 3. Ranking Engine & Profile Tune-Up
- [ ] Navigate to `/jobs` and click **Ranking Eval**.
- [ ] Confirm baseline metrics (`Recall@3 = 0.6000`, `NDCG@5 = 0.9178`, `MRR = 1.0000`).
- [ ] If you acquired a new technical certification or mastered a new framework:
  - [ ] Go to `/profile` $\to$ **Verified Skills**.
  - [ ] Add the verified skill.
  - [ ] Existing jobs will now automatically reflect higher technical match scores!

### 4. Database Backup
- [ ] Execute a quick terminal backup of your local database:
  ```powershell
  Copy-Item "storage\jobpilot.db" "storage\jobpilot_backup.db"
  ```

---

## Red Flags & Traps to Avoid

| What You Might Be Tempted To Do | Why You Should NEVER Do It | Correct Safe Alternative |
| :--- | :--- | :--- |
| **Enabling automated real submissions** | Violates ATS terms of service, risks duplicate application bans, and bypasses candidate review. | Keep `JOBPILOT_REAL_SUBMISSION_ENABLED=False`. Apply manually in 60 seconds with tailored PDF. |
| **Adding unverified skills to get higher scores** | Destroys resume credibility and fails technical interviews. Fact validator will reject the resume. | Only add skills you have actually used and can defend in a live interview. |
| **Manually editing the PDF file on disk** | Breaks the SHA-256 cryptographic checksum; triggers `ResumeIntegrityError`. | Re-tailor the resume within the app to generate a valid signed PDF. |
| **Ignoring Data Drift alerts** | Submitting an application after changing profile facts causes discrepancies. | Always re-approve an application if profile facts were updated. |
| **Running multiple backend worker processes** | Triggers duplicate APScheduler runs without distributed locking. | Run the backend with a single process via `python run.py`. |

