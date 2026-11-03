# 07 — Setup & Local Development Guide

## 1. Prerequisites & System Requirements

Before configuring JobPilot AI, ensure your development workstation meets the following prerequisites:

| Tool / Runtime | Required Version | Verification Command | Purpose |
| :--- | :--- | :--- | :--- |
| **Python** | 3.12+ (tested on 3.12.6) | `python --version` | Backend API, matching engine, reportlab PDF renderer |
| **Node.js** | 18.0+ or 20.0+ | `node --version` | Frontend Vite development server & Vitest |
| **npm** | 9.0+ or 10.0+ | `npm --version` | Frontend package manager |
| **Git** | 2.40+ | `git --version` | Version control & repository tracking |
| **Docker** (Optional) | 24.0+ | `docker --version` | PostgreSQL database container (if not using SQLite) |
| **Ollama** (Optional) | 0.3+ | `ollama --version` | Local LLM inference for semantic scoring |

---

## 2. Repository Setup & Environment Configuration

### Step 1: Clone Repository & Select Branch
Open Windows PowerShell or terminal:
```powershell
cd C:\path\to\projects
git clone https://github.com/akash-thakur09/job_finder.git
cd job_finder
git checkout feature/stop-working-for-now-in-job-pilot
```

### Step 2: Configure Environment Variables
Copy the template configuration file:
```powershell
Copy-Item .env.example .env
```
Inspect `.env`. For local development, the default values are pre-configured to use SQLite and local mock providers:
```ini
# Environment
ENVIRONMENT=development
APP_HOST=127.0.0.1
APP_PORT=8000
LOG_LEVEL=INFO

# Storage
STORAGE_DIR=./storage
RESUME_STORAGE_DIR=./storage/resumes
SCREENSHOT_STORAGE_DIR=./storage/screenshots

# Database (Default: Local SQLite)
DATABASE_URL=sqlite+aiosqlite:///storage/jobpilot.db
DATABASE_SYNC_URL=sqlite:///storage/jobpilot.db

# Safety Switches (MANDATORY ENFORCEMENT)
REQUIRE_HUMAN_APPROVAL_BEFORE_SUBMISSION=true
JOBPILOT_REAL_SUBMISSION_ENABLED=false
JOBPILOT_SYNTHETIC_DISCOVERY_ENABLED=false

# AI Configuration (Optional)
DEFAULT_AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:latest

# Email Notifications (Optional)
EMAIL_NOTIFICATIONS_ENABLED=false
EMAIL_PROVIDER=mock
```

---

## 3. Backend Setup & Database Initialization

### Step 1: Create Virtual Environment
```powershell
# From repository root
python -m venv backend\.venv

# Activate virtual environment on Windows
.\backend\.venv\Scripts\Activate.ps1
```

### Step 2: Install Backend Dependencies
```powershell
pip install --upgrade pip
pip install -r backend\requirements.txt
```

### Step 3: Run Alembic Database Migrations
Initialize or upgrade the database schema to the latest migration head (`d823fa19b2e4`):
```powershell
# Run migrations using the Alembic configuration
.\backend\.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade head

# Verify current database head
.\backend\.venv\Scripts\alembic.exe -c backend/alembic.ini current
# Output should confirm: d823fa19b2e4 (head)
```

---

## 4. Frontend Setup & Build

### Step 1: Install Node Dependencies
Open a second terminal window in the `frontend/` directory:
```powershell
cd frontend
npm install
```

### Step 2: Verify Production Build
Ensure TypeScript and Vite compile cleanly without type errors:
```powershell
npm run build
```

---

## 5. Running the Application Locally

### Starting the Backend Server
From the repository root with virtual environment activated:
```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
- Interactive Swagger API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Alternative ReDoc Documentation: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- Health Check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### Starting the Frontend Development Server
From the `frontend/` directory:
```powershell
cd frontend
npm run dev
```
- Web Application Dashboard: [http://localhost:5173](http://localhost:5173)

---

## 6. Docker & PostgreSQL Alternative Setup

If you prefer to run with PostgreSQL instead of SQLite:

1. Start the PostgreSQL container:
   ```powershell
   docker compose up -d db
   ```
2. Update your `.env` file to point to PostgreSQL:
   ```ini
   DATABASE_URL=postgresql+asyncpg://jobpilot:jobpilot_pass@localhost:5432/jobpilot_db
   DATABASE_SYNC_URL=postgresql+psycopg://jobpilot:jobpilot_pass@localhost:5432/jobpilot_db
   ```
3. Run migrations against PostgreSQL:
   ```powershell
   .\backend\.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade head
   ```

---

## 7. Running Test Suites

### Running Full Backend Test Suite (Pytest)
```powershell
# Run all 247 backend tests
.\backend\.venv\Scripts\pytest.exe backend/tests/ -v

# Run a specific test module (e.g., Indian Job Adapters)
.\backend\.venv\Scripts\pytest.exe backend/tests/test_indian_job_discovery_integration.py -v
```

### Running Frontend Test Suite (Vitest)
```powershell
cd frontend
npx vitest run
```

### Running Whitespace & Linting Verification
```powershell
git diff --check
```

---

## 8. Common Troubleshooting

| Issue / Error | Root Cause | Solution |
| :--- | :--- | :--- |
| `alembic: command not found` | Virtual environment is not activated or binary path omitted. | Use explicit path `.\backend\.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade head`. |
| `TypeError: AsyncHTTPTransport got unexpected argument 'network_backend'` | Direct keyword argument passed to transport rather than underlying `httpcore.AsyncConnectionPool`. | Verify `SSRFSafeTransport` wraps `httpcore.AsyncConnectionPool(network_backend=...)`. |
| `SSRFProtectionError: Peer IP 127.0.0.1 is prohibited` | Target URL is pointing to a local interface (`localhost`, `127.0.0.1`) without explicit test mock bypassing. | `SafeFeedFetcher` intentionally blocks loopbacks. For local test harnesses, pass `allow_http=True` or mock adapter fixtures. |
| `StaleApprovalError (HTTP 409)` | Candidate fact, job requisition, or resume PDF checksum was modified after approval was granted. | Expected security behavior. Navigate to `ApplicationQueue`, click **Reconcile**, re-review the updated diff, and grant re-approval. |
| `Ollama connection refused (11434)` | Local Ollama service is not running. | Start Ollama with `ollama serve` and pull `ollama pull llama3.1:latest`. Note: matching will continue deterministically if Ollama is absent. |
| Frontend `npm run build` memory warning | Vite chunk size exceeded 500kB. | Safe build warning regarding monolithic bundle size; does not prevent build or runtime execution. |

---

*Reference Document*: Proceed to [08_TESTING_AND_QUALITY_REPORT.md](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/docs/project-reference/08_TESTING_AND_QUALITY_REPORT.md) for complete test execution logs and verification evidence.

