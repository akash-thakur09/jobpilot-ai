# 09 — Known Limitations & Technical Debt

This document catalogs all confirmed limitations, architectural boundaries, disabled subsystems, and technical debt in JobPilot AI. It distinguishes **confirmed architectural limitations** from **suspected operational risks**.

---

## 1. Confirmed Functional Limitations

### 1. Real External Automated Submission is Disabled
- **Status**: **Disabled by Design** (`JOBPILOT_REAL_SUBMISSION_ENABLED = False`).
- **Explanation**: JobPilot AI provides an end-to-end synthetic simulation submission pipeline (`SyntheticSubmissionService` running against `mock_portal`), but does **not** perform automated form filling or file uploading against live external employer career portals (Workday, Greenhouse, Lever, Taleo, etc.).
- **Impact**: Candidates must view the requisition URL in `JobDetailModal` and apply manually if they wish to submit a live application outside synthetic simulation mode.

### 2. Manual-Import-Only for Major Indian Job Boards
- **Status**: **Architectural Boundary**.
- **Explanation**: Naukri, Instahyre, Cutshort, Foundit, and Indeed are designated as `MANUAL_IMPORT_ONLY`. They do not offer free, public, unauthenticated REST APIs. Automated headless browser scraping was explicitly rejected due to Cloudflare Bot Management and PerimeterX challenges.
- **Impact**: Discovery on these platforms relies on the candidate copying and pasting structured JSON payloads or daily email alert digests into the application.

### 3. Hirist Requires Configured RSS Feed
- **Status**: **Operational Requirement** (`CONFIGURATION_REQUIRED`).
- **Explanation**: Hirist’s web interface is a dynamic Single Page Application (SPA) without an unauthenticated global search endpoint. The adapter requires the candidate to supply a specific category RSS/Atom feed URL in source settings.

### 4. In-Process Asyncio Scheduler
- **Status**: **Architectural Boundary**.
- **Explanation**: `SchedulerService` runs in the main FastAPI Uvicorn process using Python's `asyncio.create_task`. There is no persistent message broker (e.g., Redis, Celery, RabbitMQ).
- **Impact**: If the backend process is restarted or terminates, any currently running discovery task is interrupted, and the next run timer resets according to `DISCOVERY_INTERVAL_MINUTES`.

### 5. Local-First SQLite Concurrency Limits
- **Status**: **Database Boundary**.
- **Explanation**: SQLite uses file-level locking during write transactions. While `aiosqlite` and nested savepoints handle single-user workflows smoothly, concurrent writes from multiple parallel discovery threads can occasionally encounter `sqlite3.OperationalError: database is locked` under heavy load.
- **Remedy**: For high-volume multi-board discovery, switch to PostgreSQL using the provided `docker-compose.yml` service.

### 6. Fixed Currency Exchange Rate Assumption
- **Status**: **Implementation Simplification**.
- **Explanation**: `SalaryService` uses a static conversion factor (`1 USD ≈ 83 INR`) to normalize international compensation into Indian Lakhs Per Annum (LPA). It does not poll real-time foreign exchange (Forex) APIs.

---

## 2. Incomplete or Partially Implemented Features

### 1. Semantic LLM Scoring (Ollama)
- **Status**: **Partially Implemented / Optional**.
- **Explanation**: `OllamaProvider` connects to a locally running Ollama daemon (`http://localhost:11434` with model `llama3.1:latest`).
- **Current State**: If Ollama is offline or times out, the system catches the exception and falls back to 100% deterministic rule-based scoring without interrupting user operations.
- **Technical Debt**: Fine-tuning prompts and evaluating semantic drift across different open-source model weights (e.g., Mistral, Qwen, Gemma) has not been automated.

### 2. LinkedIn Partner / OAuth Integration
- **Status**: **Partially Implemented** (`AUTHORIZATION_REQUIRED`).
- **Explanation**: The adapter schema and manual import parser are functional, but live OAuth 2.0 3-legged handshake flow is not implemented because LinkedIn requires approved developer partner status for live job search scopes.

### 3. Multi-Column PDF Templates
- **Status**: **Intentionally Omitted**.
- **Explanation**: `PdfRenderer` renders standard single-column ATS-friendly resumes using ReportLab. Visual two-column or graphic-heavy resume templates are omitted because they frequently cause parsing errors in commercial employer ATS software.

---

## 3. Suspected Risks & Operational Concerns

| Risk Area | Severity | Description | Recommended Mitigation |
| :--- | :--- | :--- | :--- |
| **SSRF in Containerized Egress** | Medium | While `SSRFSafeNetworkBackend` verifies socket peer IPs in-process, container runtimes in Kubernetes/Cloud environments can still suffer SSRF if host networking is misconfigured. | Implement defense-in-depth: enforce egress firewall rules or forward proxy policies blocking `169.254.169.254/32` at the VPC CNI layer. |
| **Frontend Bundle Size** | Low | Vite build warns that `dist/assets/index-CzAV7AfA.js` is 543 kB (>500 kB chunk threshold). | Configure code-splitting via `build.rollupOptions.output.manualChunks` to split vendor packages (Lucide, Axios, React Router). |
| **Email Credentials in Local `.env`** | Low | If SMTP notifications are configured, plain text SMTP passwords reside in `.env`. | Ensure `.env` is listed in `.gitignore` (confirmed) and never committed to version control. |
| **Resume Storage Growth** | Low | Rendered PDF files accumulate in `./storage/resumes/`. | Implement a scheduled artifact retention / cleanup policy for archived or rejected applications. |

---

## 4. Technical Debt Inventory

1. **Monolithic Router Aggregation**:
   - `backend/app/main.py` directly mounts `api_v1_router`, which imports 8 domain routers. As features expand, splitting routers into modular domain blueprints with versioned API namespaces will improve compilation and test isolation.
2. **Duplicated String Literals across Collectors**:
   - Field names (`"experience_min"`, `"salary_text"`, `"workplace_type"`) are repeated across Indian collectors. Consolidating these into typed Pydantic normalization models will improve compile-time type safety.
3. **Missing Automated Observability Metrics**:
   - Telemetry is currently stored in SQL tables (`automation_runs`, `job_sources`). Integrating standard OpenTelemetry or Prometheus `/metrics` endpoints would enable real-time dashboarding in production monitoring tools (Grafana).

---

*Reference Document*: Proceed to [10_FUTURE_ROADMAP_AND_BACKLOG.md](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/docs/project-reference/10_FUTURE_ROADMAP_AND_BACKLOG.md) for prioritized future development roadmap.

