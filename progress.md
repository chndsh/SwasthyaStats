## Task: Fix expired-session authentication bug

- **Date:** 2026-10-13
- **Status:** Completed

### Decisions

- Kept the existing authentication mechanism.
- Rejected adding a new dependency because the existing implementation
  already supported the required validation.

### Changes Made

| File | Change | Reason |
|---|---|---|
| src/auth.ts | Reject expired sessions | Prevent expired sessions from accessing protected resources |
| tests/auth.test.ts | Add regression coverage | Verify expiration behavior |

### Verification

| Check | Result | Notes |
|---|---|---|
| Authentication unit tests | Passed | Executed successfully |
| Integration tests | Blocked | Test database unavailable |
| Diff review | Passed | No unrelated changes identified |

### Final Outcome

- **Status:** Completed with limitations
- **Completed:** Expired-session validation and regression coverage.
- **Not completed:** Integration testing.
- **Verification results:** Unit tests passed; integration behavior
  remains unverified.
- **Remaining work:** Run integration tests when the test database
  becomes available.


## Task: Align prototype-architecture.md with concrete design decisions

- **Date:** 2026-10-13
- **Status:** In Progress

### Objective
Incorporate finalized architectural decisions into `prototype-architecture.md`:
1. RAG citation policy: No strict citation dropping; extract and link citations without harshly dropping uncited transitional text.
2. Privacy redaction: Non-aggressive, feasible name masking anchored to profile name and explicit header cues (`Name:`, `Patient Name:`).
3. Rate limit handling: Set document status to `rate_limited` and pause processing until a healthy key is detected via the probe ladder.
4. Client build: Flutter Web Wasm compilation (`--wasm`).
5. Upload flow: Support batch file picking in addition to sequential camera capture.
6. OCR row reconstruction: Lightweight heuristic to detect and merge vertically adjacent test-name cells before pipe-delimited emission.
7. Model weight caching: Pull dynamically on first container start onto named Docker volumes (`easyocr:`, `hf:`), keeping the Docker image leaner.
8. Groq model: No hardcoded primary model; dynamically discovered and selected from available models.

### Plan
1. Action: Update sections in `prototype-architecture.md` reflecting these decisions -> Verify: Verify diff against requirements.
2. Action: Review overall document consistency -> Verify: Ensure table of contents, diagrams, and descriptions stay coherent.

### Changes Made

| File | Change | Reason |
|---|---|---|
| `prototype-architecture.md` | Updated Section 0, 4.1, 4.2, 6, 7.0, 7.1, 7.3, 8, 11, 14 | Integrated all design choices: no strict citation dropping, feasible name masking, rate_limited pipeline pause, Wasm compilation, batch file picking, vertically adjacent test cell merging, volume model caching, and dynamic Groq model selection |

### Verification

| Check | Result | Notes |
|---|---|---|
| Section 0 Changelog | Passed | Updated table reflecting all 8 design choices |
| Section 4 (Settings & Keys) | Passed | Dynamic model discovery and `status = rate_limited` pipeline pause verified |
| Section 6 (EasyOCR) | Passed | Step 4 updated with heuristic for vertically adjacent cell merging |
| Section 7 (PWA) | Passed | Wasm compilation (`--wasm`) and batch multi-image picking documented |
| Section 8 (Privacy) | Passed | Feasible, non-aggressive redaction anchored to patient headers documented |
| Section 11 (Ask / RAG) | Passed | Relaxed citation dropping with interactive chip rendering confirmed |
| Section 14 (Workflow & Compose) | Passed | Dynamic download to named Docker volumes (`easyocr:`, `hf:`) and `--wasm` dev commands verified |

### Final Outcome

- **Status:** Completed
- **Completed:** All 8 architectural design decisions incorporated into `prototype-architecture.md`.
- **Remaining work:** None for this architecture alignment task. Ready for implementation.


## Task: Week 1 - Backend skeleton, Database schema, Settings, and Compose stack

- **Date:** 2026-10-13
- **Status:** In Progress

### Objective
Establish the backend core for Week 1:
1. Docker Compose stack (`postgres` with pgvector + `api` container).
2. FastAPI app skeleton with configuration, security, and DB engine.
3. Database models (`app_settings`, `patients`, `documents`, `document_pages`, `extractions`, `observations`, `chunks`, `llm_calls`).
4. Alembic baseline migration.
5. Fernet secrets encryption & `Settings` service with masking and env fallbacks.
6. Initial `data/lab_dictionary.json`.

### Plan
1. Action: Create `docker-compose.yml`, `api/Dockerfile`, `api/requirements.txt` -> Verify: Files created with correct dependencies and volumes.
2. Action: Create `api/app/config.py`, `api/app/db.py`, `api/app/models.py`, `api/app/security/crypto.py`, `api/app/services/settings.py` -> Verify: Importable in Python, unit checks pass.
3. Action: Set up Alembic configuration and generate baseline migration -> Verify: Alembic runs migrations successfully against postgres container.
4. Action: Implement Settings router (`/settings`, `/settings/models`, `/settings/test-llm`) and starter `lab_dictionary.json` -> Verify: Health check and test endpoints return expected status codes.
5. Action: Build Flutter Web shell with Wasm compilation and Settings screen -> Verify: Flutter tests pass and static Wasm app served by FastAPI.

### Changes Made

| File | Change | Reason |
|---|---|---|
| `docker-compose.yml` | Created Compose stack with postgres (pgvector) and api | Run containerized backend and database locally |
| `api/Dockerfile`, `api/requirements.txt` | Configured Python 3.11 with PyTorch CPU wheels & OpenCV | Lean container environment for EasyOCR and sentence-transformers |
| `api/app/config.py`, `api/app/db.py` | FastAPI BaseSettings and SQLAlchemy engine/session | App configuration, env fallbacks, and DB connection |
| `api/app/models.py` | Defined 8 tables with relationships and pgvector | Full architecture data model matching Section 9 |
| `api/app/security/crypto.py`, `api/app/security/auth.py` | Fernet secrets encryption and `X-API-Key` auth | Key encryption at rest and API protection |
| `api/app/services/settings.py` | Setting service with masked keys and presets | Provider presets, key masking, and env fallbacks |
| `api/app/llm/` | Implemented `keypool.py`, `client.py`, `probe.py` | OpenAI-compatible client, dynamic model selection, `<think>` strip, and capability ladder |
| `api/app/routers/settings.py` | `/settings`, `/settings/models`, `/settings/test-llm`, `/usage` | Provider and key management endpoints |
| `api/app/web.py`, `api/app/main.py` | StaticFiles mounting, CSP/security headers, lifespan | Serve PWA on same origin at `/` with security headers |
| `api/alembic/` | Initial migration `001_initial_schema.py` | Version-controlled database schema migrations |
| `api/data/lab_dictionary.json` | 28 common lab tests with conversions & ranges | Normalization dictionary for lab values |
| `api/tests/` | Unit and contract tests for endpoints, crypto, client | Automated test suite in Docker container |
| `app/` | Flutter Web PWA with responsive navigation and Settings screen | Week 1 PWA shell compiled with `--wasm` |

### Verification

| Check | Result | Notes |
|---|---|---|
| PostgreSQL container | Passed | Healthy, pgvector and pg_trgm extensions enabled |
| Alembic migration | Passed | Stamped and current at `001_initial_schema (head)` |
| Backend API test suite | Passed | 10 passed in 0.43s via pytest in container |
| Backend endpoints | Passed | `/health` returns 200; `/api/v1/settings` enforces `X-API-Key` header |
| Flutter test suite | Passed | Widget test passed with mock controller |
| Flutter Web Wasm build | Passed | Compiled with `flutter build web --wasm --release` |
| Same-origin static serving | Passed | Root `http://localhost:8000/` serves PWA index.html with CSP headers |

### Final Outcome

- **Status:** Completed
- **Completed:** Week 1 baseline fully implemented, running, tested, and verified.
- **Remaining work:** Week 2 (Capture, EasyOCR pipeline, row reconstruction, and background processing).


## Task: Week 2 - Capture, Normalization, EasyOCR Engine, and Document Processing

- **Date:** 2026-10-14
- **Status:** In Progress

### Objective
Implement Week 2 deliverables according to `prototype-architecture.md`:
1. Multi-page document upload (images/PDF) and page normalization (EXIF, deskew, grayscale, CLAHE, 2000-2500px).
2. Page image retrieval endpoint `GET /api/v1/documents/{id}/pages/{page_no}.png`.
3. `EasyOcrEngine` with model caching on named volume (`/root/.EasyOCR`).
4. Row reconstruction with median-height clustering and vertically adjacent test cell merging.
5. Background processing pipeline with status progression (`queued` -> `normalizing` -> `ocr`).
6. Document management endpoints (`POST /documents`, `GET /documents/{id}`, `GET /documents`).
7. OCR evaluation benchmark script (`eval/run_eval.py`).
8. Flutter PWA capture & document view screen.

### Plan
1. Action: Implement image normalization (`api/app/services/image_processing.py`) handling EXIF rotation, CLAHE, resizing, and PDF splitting -> Verify: Unit tests with synthetic test image and PDF.
2. Action: Implement EasyOCR wrapper and row reconstruction (`api/app/ocr/engine.py`, `api/app/ocr/reconstruct.py`) -> Verify: Unit tests for cell clustering and vertical header merge.
3. Action: Implement Document service and router (`api/app/services/documents.py`, `api/app/routers/documents.py`) with BackgroundTasks -> Verify: API tests for upload, background status update, and page image streaming.
4. Action: Implement OCR eval script (`eval/run_eval.py`) with sample synthetic report -> Verify: CLI eval run with accuracy metrics.
5. Action: Implement Flutter capture and document views -> Verify: Flutter tests pass and `flutter build web --wasm --release` succeeds.

### Changes Made

| File | Change | Reason |
|---|---|---|
| `docker-compose.yml` | Added `PYTHONPATH: /app` | Ensure direct pytest execution in container |
| `api/pytest.ini` | Added pytest config | Python path and test discovery |

### Verification

| Check | Result | Notes |
|---|---|---|
| Week 1 backend test suite | Passed | 10/10 tests passed via `docker compose exec -T api pytest` |
| Week 1 Flutter test suite | Passed | All widget tests passed |
| Week 1 Alembic migration | Passed | Database schema current at head |
| Week 1 Health endpoint | Passed | `curl http://localhost:8000/health` returns 200 OK |