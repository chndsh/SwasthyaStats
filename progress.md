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
- **Status:** Completed

### Objective
Implement Week 2 deliverables according to `prototype-architecture.md`:
1. Multi-page document upload (images/PDF) and page normalization (EXIF, deskew, grayscale, CLAHE, 2000-2500px).
2. Page image retrieval endpoint `GET /api/v1/documents/{id}/pages/{page_no}.png`.
3. `EasyOcrEngine` with model caching on named volume (`/root/.EasyOCR`).
4. Row reconstruction with median-height clustering and vertically adjacent test cell merging.
5. Background processing pipeline with status progression (`queued` -> `normalizing` -> `ocr` -> `needs_review`).
6. Document management endpoints (`POST /documents`, `GET /documents/{id}`, `GET /documents`).
7. OCR evaluation benchmark script (`eval/run_eval.py`).
8. Flutter PWA capture & document view screen.

### Decisions Made
- Reconstructed rows cluster cells within 0.5 × median box height, and merge vertically adjacent test-name cells when column 1 text wraps without intervening numbers.
- Ingestion enforces a 12 MB total upload limit and maximum 10 pages per document.
- EasyOCR PyTorch models load into `/root/.EasyOCR` volume, ensuring models persist across container restarts.
- Flutter PWA compiles to WebAssembly (`--wasm`) with Dio fetching page images directly via the backend API key header for `Image.memory` rendering.

### Changes Made

| File | Change | Reason |
|---|---|---|
| `api/app/pipeline/normalize_pages.py` | EXIF rotation, deskew, grayscale, CLAHE, aspect-preserving resize, PDF splitting | Image preparation and normalization pipeline |
| `api/app/pipeline/ocr/base.py` | `OcrBox`, `OcrLine`, `OcrEngine` protocols | Core OCR data types |
| `api/app/pipeline/ocr/rows.py` | Row clustering and vertical test header merge heuristic | Format table rows delimited by ` \| ` |
| `api/app/pipeline/ocr/easyocr_engine.py` | EasyOCR engine wrapper with volume model caching | EasyOCR execution and bounding box extraction |
| `api/app/services/documents.py` | Document upload validation and async background pipeline | Manage document lifecycle and page persistence |
| `api/app/routers/documents.py` | `/documents`, `/documents/{id}`, `/documents/{id}/pages/{page_no}.png` | REST endpoints for documents and page streaming |
| `api/app/schemas.py` | `DocumentRead`, `DocumentPageRead`, `DocumentUploadResponse` | Pydantic V2 schemas for document API |
| `api/app/main.py` | Mounted `documents.router` | Expose document API endpoints |
| `eval/run_eval.py`, `eval/RESULTS.md` | OCR accuracy evaluation benchmark and results log | Quantify numeric, unit, and row accuracy |
| `eval/samples/`, `eval/ground_truth/` | Synthetic lab report image and ground truth JSON | Evaluation benchmark test fixtures |
| `app/lib/features/documents/` | `document_model.dart`, `documents_controller.dart`, `documents_screen.dart`, `document_view_screen.dart` | Flutter PWA documents list, camera capture, batch picker, and image viewer |
| `app/lib/features/navigation/app_router.dart` | Wired `/documents` and `/documents/:id` routes | PWA navigation routes |
| `api/tests/` | `test_normalize_pages.py`, `test_ocr_reconstruction.py`, `test_documents_api.py`, `test_eval_harness.py` | Full backend unit and contract test coverage |
| `app/test/documents_screen_test.dart` | Flutter widget test for documents screen | Verify documents list rendering and status chips |

### Verification

| Check | Result | Notes |
|---|---|---|
| Backend Pytest Suite | Passed | 18/18 tests passed in 10.73s via `docker compose exec -T api pytest -v` |
| Flutter Test Suite | Passed | 2/2 tests passed (`documents_screen_test.dart` & `widget_test.dart`) |
| Flutter Web Wasm Build | Passed | `flutter build web --wasm --release` succeeded in 32.9s |
| EasyOCR Benchmark | Passed | Evaluated on `sample_lab_report.png`: 100% unit accuracy, 100% row grouping accuracy, 75% numeric accuracy |
| Page Image Streaming | Passed | `GET /api/v1/documents/{id}/pages/1.png` returns normalized PNG |
| Background Pipeline | Passed | Upload transitions `queued` -> `normalizing` -> `ocr` -> `needs_review` |

### Final Outcome
- **Status:** Completed
- **Completed:** All Week 2 deliverables implemented, tested, verified end-to-end, and compiled.
- **Remaining work:** Week 3 (Extraction via external LLM, grounding check, dictionary normalization, and review screen).