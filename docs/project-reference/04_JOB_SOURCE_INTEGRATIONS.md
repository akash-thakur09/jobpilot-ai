# 04 — Job Source Integrations Specification

## 1. Overview & Integration Philosophy

JobPilot AI connects to both global ATS platforms and major Indian job platforms. The project adheres to a strict engineering and ethical policy: **it does not perform unauthorized, brittle web scraping against anti-bot protected portals**.

Aggressive scraping against platforms protected by Cloudflare Bot Management, PerimeterX, or Akamai leads to IP bans, captcha challenges, and platform terms-of-service violations. Instead, JobPilot AI classifies each job source by its true technical integration status:

1. **`ACTIVE_POLLING`**: Automated periodic polling against documented, permitted public ATS endpoints (Greenhouse, Lever).
2. **`CONFIGURATION_REQUIRED`**: Automated polling only after the candidate configures a valid public RSS/Atom feed URL (Hirist).
3. **`AUTHORIZATION_REQUIRED`**: Requires authorized candidate OAuth tokens or credentials; falls back to structured manual ingestion (LinkedIn).
4. **`MANUAL_IMPORT_ONLY`**: Dedicated manual ingestion pipeline for structured JSON payloads and copy-pasted email alert digests (Naukri, Instahyre, Cutshort, Foundit, Indeed).
5. **`SYNTHETIC_TEST`**: Local deterministic test fixture generator for offline testing.

---

## 2. Source-by-Source Integration Matrix

| Source | Identifier | Integration Status | Ingestion Mechanism | Default Enabled | Rate Limit (RPM) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Greenhouse** | `greenhouse` | `ACTIVE_POLLING` | Permitted Public Board Token API | `True` | 60 |
| **Lever** | `lever` | `ACTIVE_POLLING` | Permitted Public Site API | `True` | 60 |
| **Hirist** | `hirist` | `CONFIGURATION_REQUIRED` | User-Configured RSS/Atom Feed | `True` | 30 |
| **Naukri** | `naukri` | `MANUAL_IMPORT_ONLY` | Structured JSON & Email Alert Digest | `True` | N/A (Manual) |
| **Instahyre** | `instahyre` | `MANUAL_IMPORT_ONLY` | Structured JSON & Email Alert Digest | `True` | N/A (Manual) |
| **Cutshort** | `cutshort` | `MANUAL_IMPORT_ONLY` | Structured JSON & Email Alert Digest | `True` | N/A (Manual) |
| **Foundit** | `foundit` | `MANUAL_IMPORT_ONLY` | Structured JSON & Email Alert Digest | `True` | N/A (Manual) |
| **Indeed** | `indeed` | `MANUAL_IMPORT_ONLY` | Structured JSON & Email Alert Digest | `True` | N/A (Manual) |
| **LinkedIn** | `linkedin` | `AUTHORIZATION_REQUIRED` | Manual JSON & Alert Digest (OAuth Staged) | `True` | N/A (Manual) |
| **Synthetic** | `synthetic` | `SYNTHETIC_TEST` | Local In-Memory Test Fixture Generator | `False` | 120 |

---

## 3. Detailed Source Specifications

### 1. Greenhouse (`greenhouse`)
- **Adapter File**: [`backend/app/collectors/greenhouse.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/greenhouse.py)
- **Integration Mode**: Permitted Public Board Token API
- **Endpoint**: `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`
- **How It Works**:
  - The candidate or administrator configures target company board tokens in `job_sources.config_json` (e.g., `{"boards": ["canonical", "stripe", "gitlab"]}`).
  - During discovery, the adapter iterates configured tokens, fetches open positions with full HTML descriptions, and normalizes them into `NormalizedJob` records.
- **Rate Limit**: 60 requests per minute.
- **Error Isolation**: Failure on one board token (e.g., 404 Not Found) is isolated; subsequent boards continue execution.
- **Tests**: [`backend/tests/test_multi_board_discovery.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_multi_board_discovery.py), [`backend/tests/test_live_sources_and_adapters.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_live_sources_and_adapters.py)

---

### 2. Lever (`lever`)
- **Adapter File**: [`backend/app/collectors/lever.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/lever.py)
- **Integration Mode**: Permitted Public Site API
- **Endpoint**: `https://api.lever.co/v0/postings/{site_token}?mode=json`
- **How It Works**:
  - Configured with company site tokens in `config_json` (e.g., `{"sites": ["netflix", "palantir"]}`).
  - Ingests JSON arrays containing job titles, workplace categories, and rich text descriptions.
- **Rate Limit**: 60 requests per minute.
- **Tests**: [`backend/tests/test_multi_board_discovery.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_multi_board_discovery.py)

---

### 3. Hirist (`hirist`)
- **Adapter File**: [`backend/app/collectors/hirist.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/hirist.py)
- **Integration Mode**: User-Configured RSS/Atom Feed (`CONFIGURATION_REQUIRED`)
- **How It Works**:
  - Hirist’s main web portal is an Angular/React SPA that requires authentication for direct search APIs. However, candidates can generate category RSS/Atom alert feeds.
  - The adapter takes a candidate-configured feed URL (`rss_url` or `feed_url` in `config_json`).
  - Fetches the XML feed via `SafeFeedFetcher` and parses items using `safe_parse_xml()`.
  - Normalizes titles formatted as `"Company - Role - Location"`, extracts INR salary text (e.g., `"20 - 35 LPA"`), and records jobs.
- **Rate Limit**: 30 requests per minute.
- **Network Security**: Strict SSRF and XXE prevention enforced via `SafeFeedFetcher` and `safe_parse_xml`.
- **Tests**: [`backend/tests/test_indian_job_discovery_integration.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_discovery_integration.py)

---

### 4. Naukri (`naukri`)
- **Adapter File**: [`backend/app/collectors/naukri.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/naukri.py)
- **Integration Mode**: `MANUAL_IMPORT_ONLY`
- **Why Not Automated Scraping?**: Naukri employs aggressive Cloudflare and Akamai bot protections, dynamic JavaScript rendering, and requires session cookies. Automated scrapers trigger instant 403 blocks and risk account/IP blacklisting.
- **How It Works**:
  - The candidate uses the **Import Jobs** modal in the web dashboard or calls `POST /api/v1/jobs/sources/naukri/import`.
  - Ingests structured JSON (exported via browser console or extensions) or copy-pasted text from **Naukri Daily Job Alert Emails**.
  - `parse_email_alert_jobs()` extracts `Role`, `Company`, `Location`, `Salary (INR LPA)`, `Experience`, and `URL`.
- **Automated Polling Behavior**: Automated polling is explicitly skipped; `DiscoveryMatchingPipeline` records `SKIPPED_MANUAL_IMPORT_ONLY` with 0 discovered jobs.
- **Tests**: [`backend/tests/test_indian_job_adapters.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_adapters.py)

---

### 5. Instahyre (`instahyre`)
- **Adapter File**: [`backend/app/collectors/instahyre.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/instahyre.py)
- **Integration Mode**: `MANUAL_IMPORT_ONLY`
- **How It Works**:
  - Instahyre matches candidates based on registered candidate profiles and delivers opportunities via email notifications.
  - Supports manual import of structured opportunity JSON and email alert digest text.
  - Normalizes compensation packages into `INR` with min/max LPA parsing.
- **Tests**: [`backend/tests/test_indian_job_adapters.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_adapters.py)

---

### 6. Cutshort (`cutshort`)
- **Adapter File**: [`backend/app/collectors/cutshort.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/cutshort.py)
- **Integration Mode**: `MANUAL_IMPORT_ONLY`
- **How It Works**:
  - Cutshort operates as an AI-driven matchmaking community with private chat channels.
  - Accepts manual JSON payloads and email alert text.
  - Cleans HTML markup, normalizes canonical URLs to `https://cutshort.io/job/...`, and extracts tech stack requirements.
- **Tests**: [`backend/tests/test_indian_job_adapters.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_adapters.py)

---

### 7. Foundit (`foundit`, formerly Monster India)
- **Adapter File**: [`backend/app/collectors/foundit.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/foundit.py)
- **Integration Mode**: `MANUAL_IMPORT_ONLY`
- **How It Works**:
  - Ingests structured JSON exports and email digests.
  - Normalizes location strings (e.g., "Bangalore / Bengaluru", "Hyderabad / Secunderabad") into canonical Indian metropolitan names.
- **Tests**: [`backend/tests/test_indian_job_adapters.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_adapters.py)

---

### 8. Indeed (`indeed`)
- **Adapter File**: [`backend/app/collectors/indeed.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/indeed.py)
- **Integration Mode**: `MANUAL_IMPORT_ONLY`
- **Audit Finding**: Legacy Indeed Publisher Job Search API (`api.indeed.com/ads/apisearch`) has been retired and is unavailable for new integrations.
- **How It Works**:
  - Legacy publisher ID endpoint construction was completely removed.
  - Classified as `MANUAL_IMPORT_ONLY`.
  - Supports structured JSON imports and copy-pasted Indeed Job Alert emails.
  - Automated polling is skipped during scheduled discovery.
- **Tests**: [`backend/tests/test_indian_job_adapters.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_adapters.py)

---

### 9. LinkedIn (`linkedin`)
- **Adapter File**: [`backend/app/collectors/linkedin.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/collectors/linkedin.py)
- **Integration Mode**: `AUTHORIZATION_REQUIRED`
- **How It Works**:
  - LinkedIn requires authorized partner API access or candidate OAuth session tokens.
  - Without valid OAuth credentials, automated polling is safely skipped.
  - The adapter fully supports importing LinkedIn Job Alert emails and structured job JSON.
  - Sanitizes LinkedIn tracking parameters (`?trackingId=...`, `?refId=...`).
- **Tests**: [`backend/tests/test_indian_job_adapters.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/tests/test_indian_job_adapters.py)

---

## 4. SSRF & Network Security Protections

Any adapter making outbound network connections (such as `HiristJobAdapter` or `GreenhouseJobAdapter`) routes requests through **`SafeFeedFetcher`** in [`backend/app/core/network_security.py`](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/backend/app/core/network_security.py).

### Enforced Protections
1. **Scheme Restriction**: HTTPS required by default (`allow_http=False`).
2. **URL Credential Rejection**: URLs with embedded usernames or passwords (`https://user:pass@host/`) are rejected with `SSRFProtectionError`.
3. **Loopback & Private Network Blocking**:
   - Rejects `127.0.0.0/8`, `::1`.
   - Rejects RFC 1918 private subnets: `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.
   - Rejects link-local subnets: `169.254.0.0/16`, `fe80::/10`.
   - Rejects IPv4-mapped IPv6 representations (`::ffff:127.0.0.1`, `::ffff:169.254.169.254`).
   - Rejects 6to4 (`2002::/16`) subnets embedding private IPv4 addresses.
4. **Cloud Metadata IP Blocking**:
   - AWS / GCP / Azure: `169.254.169.254`
   - AWS ECS Task Metadata: `169.254.170.2`
   - Alibaba Cloud: `100.100.100.200`
   - GCP Metadata Hostname: `metadata.google.internal`
5. **Connection-Time Socket Peer IP Validation (Defeating DNS Rebinding)**:
   - Mounts `SSRFSafeTransport` powered by `SSRFSafeNetworkBackend(AnyIOBackend)`.
   - Immediately upon TCP socket connection, inspects `stream.get_extra_info("server_addr")`. If the destination IP is prohibited, the socket is dropped before TLS handshake or HTTP transmission.
6. **Redirect Revalidation**:
   - Each hop in a 301/302 redirect chain is individually revalidated. Maximum 5 redirect hops.
7. **Decompression Bomb Protection**:
   - Inspects `Content-Length` header upfront.
   - Enforces streaming byte limit `MAX_RESPONSE_BYTES = 5 * 1024 * 1024` (5 MB) on decoded chunks.
8. **XXE & XML Entity Disabling**:
   - `safe_parse_xml()` scans XML payloads and prohibits `<!DOCTYPE` and `<!ENTITY` definitions.

---

*Reference Document*: Proceed to [05_AI_MATCHING_AND_RESUME_GENERATION.md](file:///c:/Users/imaka/Desktop/Desk/PROJECTS/JobPilot_AI/job_finder/docs/project-reference/05_AI_MATCHING_AND_RESUME_GENERATION.md) for matching algorithms and resume tailoring details.
