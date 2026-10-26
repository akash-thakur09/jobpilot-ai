# JobPilot AI

JobPilot AI is a local-first, privacy-focused personal AI job-hunting agent. It continuously discovers relevant job openings across supported job platforms, evaluates them against a verified candidate profile with explainable scoring, generates tailored ATS-friendly resumes grounded strictly in verified facts, and automates permitted application workflows while enforcing human approval before final submission.

---

## Key Features

- **Local-First & Privacy Preserving**: Candidate data, generated resumes, and AI inference run locally on your machine via Ollama (`llama3.1`).
- **Factually Grounded Resumes**: Zero hallucination policy. Resumes only highlight verified skills, achievements, and career history without inventing qualifications.
- **Explainable Match Scoring**: Deterministic rules for mandatory eligibility combined with weighted scoring for skills, experience, and remote/location preferences.
- **Immutable Application History**: Every submitted application preserves the exact resume version, PDF file, and SHA-256 checksum used at submission time.
- **Safe Browser Automation**: Uses Playwright for form filling and resume uploading, strictly enforcing human approval before final submission.
- **Multi-Source Job Discovery**: Adapters for public APIs, company career pages (Greenhouse, Lever), and scheduled discovery.

---

## Quickstart

### Prerequisites
- **Python 3.12+**
- **Node.js 20+** & **npm**
- **Ollama** with `llama3.1:latest` (`ollama run llama3.1`)
- **Docker** (optional, for containerized PostgreSQL) or local PostgreSQL / SQLite for lightweight development

### 1. Clone & Configure
```bash
git clone <repo-url> jobpilot-ai
cd jobpilot-ai
cp .env.example .env
```

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup
```bash
cd ../frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and the backend API documentation at `http://localhost:8000/docs`.

---

## Core API Endpoints (v1)

### Candidate Profile
- `GET /api/v1/profile` — Retrieve current verified candidate profile
- `POST /api/v1/profile` — Create candidate profile
- `PATCH /api/v1/profile` — Update candidate profile fields
- `POST /api/v1/profile/skills` — Add verified technical or soft skill
- `DELETE /api/v1/profile/skills/{skill_id}` — Delete skill
- `POST /api/v1/profile/experiences` — Add employment history
- `POST /api/v1/profile/educations` — Add education record
- `POST /api/v1/profile/projects` — Add demonstrable project
- `POST /api/v1/profile/import-resume` — Upload & extract master PDF resume into unverified review draft
- `POST /api/v1/profile/import-resume/confirm` — Confirm and save draft as verified profile

### Job Discovery & Management
- `GET /api/v1/jobs` — List jobs with search, company/remote filters, and pagination
- `GET /api/v1/jobs/{job_id}` — Retrieve full job details and requirements
- `GET /api/v1/jobs/sources` — List registered discovery sources and their health
- `POST /api/v1/jobs/discover` — Trigger job discovery for `synthetic`, `greenhouse`, or `lever`

### Job Matching & Scoring
- `POST /api/v1/matching/evaluate/{job_id}` — Evaluate a single job against the candidate profile
- `POST /api/v1/matching/evaluate-all` — Batch-evaluate all discovered jobs
- `GET /api/v1/matching/results` — List match evaluations (with `is_eligible`, `min_score`, pagination)
- `GET /api/v1/matching/results/{job_id}` — Get latest match score and breakdown for a job
- `GET /api/v1/matching/health` — Check matching engine and Ollama AI provider status

---

## Documentation
- [Project Specification](docs/PROJECT_SPEC.md)
- [Development Progress Checklist](docs/DEVELOPMENT_PROGRESS.md)

---

## License
MIT License.
