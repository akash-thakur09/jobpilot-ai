# JobPilot AI — Living Project Specification

## 1. System Overview
JobPilot AI is a local-first, privacy-focused personal AI job-hunting agent. It continuously discovers relevant job openings across supported job platforms, evaluates them against a verified candidate profile with explainable scoring, generates tailored ATS-friendly resumes grounded strictly in verified facts, and automates permitted application workflows while enforcing human approval before final submission.

## 2. Architecture & Design Principles
- **Local-first & Privacy**: Candidate profiles, resumes, application history, and local AI model inference (Ollama with `llama3.1`) stay on the local machine by default. No candidate data is sent to cloud LLMs unless explicitly configured.
- **Factually Grounded**: Zero hallucination policy. Resumes and application answers must only use verified candidate facts, skills, employment dates, and metrics.
- **Auditable & Immutable Application Records**: Once a resume is generated and submitted, its exact content, SHA-256 checksum, and PDF file remain immutable. Master profile updates never retroactively mutate submitted historical records.
- **Deterministic Matcher**: Hard eligibility filters (mandatory skills, location, work authorization) are strictly deterministic; semantic matching supplements scoring without overriding constraints.
- **Safe Browser Automation**: Uses Playwright behind adapter interfaces. Requires explicit human confirmation before final submission. Never bypasses anti-bot, CAPTCHA, or platform terms of service.

## 3. Technology Stack
- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic, PostgreSQL (with SQLite compatibility fallback for lightweight testing/environments), APScheduler.
- **Frontend**: React 18 / 19, TypeScript (strict mode), Vite, Tailwind CSS, Lucide icons.
- **AI & Document Processing**: Ollama (`llama3.1:latest` verified on local machine), ReportLab / WeasyPrint / FPDF2 for robust ATS PDF generation, pdfplumber / pypdf for text extraction verification.
- **Browser Automation**: Playwright (Chromium).
- **Testing**: pytest, pytest-asyncio, Playwright mock harnesses.

## 4. Domain Models & Relationships
1. **CandidateProfile**: Name, contact, summary, work authorization, location, remote preferences, target titles, target salary, years of experience.
2. **CandidateSkill**: Skill name, category (technical/soft), years experience, verified flag.
3. **CandidateExperience**: Company, role, location, start/end date, is_current, verified achievements/bullets.
4. **CandidateEducation**: Institution, degree, field of study, graduation year.
5. **CandidateProject**: Title, description, technologies, URL, verifiable outcomes.
6. **JobSource**: Source adapter identifier (e.g. `greenhouse`, `lever`, `feed_synthetic`), name, base URL, rate limits, enabled status.
7. **Job**: Unique source + external_id, title, company, canonical URL, location, remote status, description, requirements, salary range, status (DISCOVERED, INGESTED, EXPIRED).
8. **MatchScore**: Job ID + Candidate ID, total score (0-100), matching skills, missing skills, hard filter pass/fail, reasoning breakdown.
9. **ResumeVersion**: Unique ID, Job ID, Candidate snapshot, structured content (JSON), PDF path, SHA-256 checksum, ATS validation status, created_at.
10. **Application**: Unique ID, Job ID, ResumeVersion ID, state, submission_date, portal_type, notes.
11. **ApplicationEvent**: Application ID, state transition (from_state -> to_state), timestamp, actor (system/human), payload/diagnostics.
12. **AutomationRun**: Run ID, job counts, status, start/end timestamps, error logs.

## 5. Application Workflow State Machine
`DISCOVERED` -> `SCORED` -> `RESUME_GENERATED` -> `READY_FOR_REVIEW` -> `APPROVED` -> `SUBMISSION_PENDING` -> `SUBMITTED`
Alternative branches:
- `NEEDS_HUMAN_ACTION` (missing answer, CAPTCHA detected, ambiguous form)
- `FAILED` (network failure, submission error, unrecoverable)
- Post-submission states: `SHORTLISTED`, `INTERVIEW_SCHEDULED`, `REJECTED`, `WITHDRAWN`

## 6. Directory Structure
```
job_finder/
  backend/
    app/
      api/          # FastAPI routers (v1 endpoints)
      core/         # Config, logging, security, errors
      db/           # Database session, base model
      models/       # SQLAlchemy 2.0 declarative models
      schemas/      # Pydantic v2 schemas
      services/     # Business logic (Profile, Matching, Resume, AppWorkflow)
      providers/    # AI provider abstraction (Ollama, mock)
      collectors/   # Job discovery source adapters
      resumes/      # PDF builder and ATS text validator
      automation/   # Playwright form automation adapters
      notifications/# Local & notification service
    alembic/        # Migrations
    tests/          # Pytest suite
    pyproject.toml  # Python project configuration
  frontend/
    src/
      api/          # Typed API client
      components/   # UI components
      pages/        # Dashboard, Jobs, Resumes, Applications, Settings
      types/        # TypeScript interfaces
    package.json
    vite.config.ts
    tailwind.config.js
  storage/
    resumes/        # Immutable generated PDF storage
    screenshots/    # Automation review artifacts
  docs/
    PROJECT_SPEC.md
    DEVELOPMENT_PROGRESS.md
  docker-compose.yml
  .env.example
  .gitignore
  README.md
```

## 7. Known Risks & Mitigations
- **Docker Desktop Availability**: On Windows, Docker Desktop Linux engine may not always be running. Backend will support both PostgreSQL and local connection options with explicit health checking.
- **ATS Parsing Inconsistencies**: Ensure generated resumes are single-column, clear standard headings, standard system fonts, avoiding nested tables or multi-column layouts that confuse parsers.
- **Job Board Bot Protections**: Adhere to terms of service; support public career APIs (Greenhouse, Lever) and user-supplied URLs rather than aggressive scraping. Pauses for human intervention when forms are complex or blocked.
