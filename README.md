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

## Documentation
- [Project Specification](docs/PROJECT_SPEC.md)
- [Development Progress Checklist](docs/DEVELOPMENT_PROGRESS.md)

---

## License
MIT License.
