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
### 2026-10-14 — Week 2 Review + Fixes (session continued)

**Self-review performed** (pro model quota exhausted, reviewer subagent returned 429):
- I-1 fixed: reject `len(files) > MAX_PAGES` before any DB write → `400 Bad Request`
- I-2 fixed: PIL `verify()` each image synchronously before creating `Document` record → `400 Bad Request` on corrupt files
- M-1 verified: `ocr_lines` column is `JSONB` — no issue
- M-2 noted: TODO comment added in `rows.py` for 3-line wrap limitation
- M-3, M-4 deferred to Week 3

**Commit:** `aa25761` — `fix(api): reject over-limit file count and corrupt images before DB commit`
**Tests:** 18/18 backend passed post-fix

**Week 2 milestone: COMPLETE ✅**

## Task: Week 3 - Extraction, Grounding, Review Screen, and Bake-offs

- **Date:** 2026-10-16
- **Status:** Completed

### Objective
Implement Week 3 deliverables according to `prototype-architecture.md`:
1. PII Redaction stage on CPU before sending OCR lines to external LLM.
2. Structured LLM extraction with fallback ladder (`strict structured_outputs` -> `json_object` fallback).
3. Grounding check on numeric values against OCR lines, lab dictionary canonical normalization, and confidence calculation.
4. Pipeline integration with rate-limit detection (`rate_limited` status pause and resume capability).
5. Review & Confirm endpoints (`GET /documents/{id}/extractions`, `PATCH /observations/{id}`, `POST /documents/{id}/confirm`, `POST /documents/{id}/retry`).
6. Flutter Web Review screen with responsive layout (split-pane on wide screens, stacked on mobile), observation editing dialog, and confirm flow.
7. Usage panel and `rate_limited` status badge with retry trigger in Flutter documents screen.
8. Extraction evaluation bake-off harness and F1 metrics logging (`eval/run_eval.py`, `eval/RESULTS.md`).

### Decisions Made
- Defer concurrency semaphore (`llm.concurrency`) to later; process multi-page extraction sequentially per page.
- Redaction runs purely on CPU with regex anchored to patient name and standard PII patterns before passing text to the LLM.
- Grounding check validates that numeric strings exist in referenced OCR lines; ungrounded observations receive a heavy confidence penalty (`min(raw_conf * 0.5, 0.45)`) so they are flagged for human review.
- Observation editing after confirmation is blocked with `409 Conflict` to guarantee audit trail integrity.
- Review screen is responsive: top-image/bottom-list on mobile, side-by-side on wide screens.
- API Key authorization logic (`api/app/security/auth.py`) enforces the key when configured, properly rejecting missing or invalid keys.
- Mounted lab dictionary inside container at `api/app/data/lab_dictionary.json` to ensure clean runtime loading.

### Changes Made

| File | Change | Reason |
|---|---|---|
| `api/app/pipeline/redact.py` | CPU regex redaction for patient name and PII | Prevent PHI leakage to external LLM providers |
| `api/app/pipeline/extract.py` | Pydantic extraction schema, system prompt, and fallback ladder | Structured observation extraction from OCR text |
| `api/app/pipeline/normalize.py` | Grounding check, dictionary alias lookup, confidence scorer | Link extracted data to OCR evidence & canonical tests |
| `api/app/services/documents.py` | Integrated extraction into background processing worker with rate-limit pausing | End-to-end document processing pipeline |
| `api/app/routers/documents.py` | Added extraction inspection, document confirmation, and retry endpoints | Review workflow API endpoints |
| `api/app/routers/observations.py` | Added observation patch endpoint with 409 conflict check | Allow user corrections before confirmation |
| `api/app/security/auth.py` | Fixed API key bypass regression when key is configured | Enforce secure access control |
| `api/data/lab_dictionary.json` & `api/app/data/lab_dictionary.json` | Updated lab test aliases and ranges | Canonical test normalization |
| `app/lib/features/review/*` | Review screen, controller, models, and responsive widgets | Interactive observation review & confirmation UI |
| `app/lib/features/navigation/app_router.dart` | Added `/documents/:id/review` route | Route navigation to review screen |
| `app/lib/features/documents/documents_screen.dart` | Added `rate_limited` chip, retry action, and navigation to review | Document status indicators and retry flow |
| `eval/run_eval.py`, `eval/RESULTS.md` | Extraction F1 evaluation scoring and bake-off benchmark | Track extraction precision, recall, and F1 |
| `api/tests/*` | 36 unit and contract tests covering all pipeline and API components | Automated backend test suite |
| `app/test/*` | 4 widget and controller tests covering review and documents screens | Automated frontend test suite |

### Verification

| Check | Result | Notes |
|---|---|---|
| Backend Pytest Suite | Passed | 36/36 tests passed in 11.65s via `docker compose exec -T api pytest -v` |
| Flutter Test Suite | Passed | 4/4 tests passed via `flutter test` |
| Flutter Web Wasm Build | Passed | `flutter build web --wasm --release` succeeded in 37.0s |
| Redaction Unit Tests | Passed | Verified patient name and contact info masking while preserving numeric lab values |
| Grounding & Normalization Tests | Passed | Verified numeric grounding match and alias-to-canonical normalization |
| Rate-Limit Handling Tests | Passed | Verified document transitions to `rate_limited` when LLM keys are exhausted |
| Review Endpoints Contract Tests | Passed | Verified extraction retrieval, observation patch, confirmation, and 409 conflict on confirmed observation edit |
| Evaluation F1 Harness | Passed | Verified extraction F1 calculation on benchmark fixtures |

### Final Outcome

- **Status:** Completed
- **Completed:** Week 3 milestone fully implemented, verified, and compiled.
- **Commit History:**
  - `c26d184` — `fix(security): enforce X-API-Key validation when configured`
  - `4c5c2c5` — `feat(pipeline): add PII redaction for OCR text before LLM extraction`
  - `901afc5` — `feat(pipeline): add LLM extraction schemas, prompt, and fallback ladder`
  - `f98b370` — `feat(pipeline): add grounding check, dictionary normalization, and confidence scoring`
  - `c09f368` — `feat(pipeline): integrate extraction stage with rate-limit handling into background worker`
  - `9e4c413` — `feat(api): add extraction, observation edit, confirm, and retry endpoints`
  - `b166a7e` — `feat(flutter): add review screen with observation editing and confirm flow`
  - `b1e79ad` — `feat(flutter): show rate_limited chip with retry, wire usage panel in settings`
  - `b355dab` — `eval: add extraction F1 scoring and log Week 3 bake-off results`

**Week 3 milestone: COMPLETE ✅**

## Task: Pipeline Reliability & Stuck Extraction Diagnostics

- **Date:** 2026-10-17
- **Status:** Completed

### Objective
Diagnose and resolve background pipeline issues causing documents to hang at `extracting` status in the Flutter Web UI and ensure resilient rate-limit handling and caching.

### Root Causes Identified
1. **PostgreSQL Type Mismatch in Daily Token Queries:**
   - In `api/app/llm/client.py` and `api/app/routers/settings.py`, `LlmCall.created_at >= time.strftime(...)` passed a `str` instead of a timezone-aware `datetime`, causing Postgres psycopg to throw `operator does not exist: timestamp with time zone >= character varying`.
2. **Aborted Transaction Propagation (`InFailedSqlTransaction`):**
   - When an exception occurred during extraction, handlers executed `doc.status = "failed"` and `db.commit()` without preceding `db.rollback()`. In psycopg, an aborted transaction rejects further queries, crashing the handler and leaving the document stuck in `extracting` forever.
3. **Groq Strict Schema Rejection:**
   - Groq structured outputs rejected `LabReportRaw` with HTTP 400 because nested models in `$defs` lacked `additionalProperties: false` or complete `required` arrays.
4. **Error Detail Swallowing in `KeyPool`:**
   - When an API key encountered a 429 or auth failure, subsequent attempts failed with a generic `ValueError("All configured API keys are currently exhausted, rate-limited, or invalid.")`, masking the underlying provider error.
5. **Multi-page Atomic Rollback Token Loss:**
   - Multi-page documents committed extractions only after all pages completed. A rate limit on page 2 or 3 discarded page 1's observations, requiring full re-extraction on retry.
6. **Frontend Polling Gap:**
   - `documents_controller.dart` polled on `queued`, `normalizing`, and `ocr`, but omitted `extracting`.

### Decisions & Solutions
- **Postgres Timestamptz:** Switched `LlmCall.created_at` filters to `datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)`.
- **Transaction Rollback Guard:** Added explicit `db.rollback()` before updating document status in all error handlers across `services/documents.py`.
- **Strict Schema Transformer:** Added `to_strict_json_schema()` in `extract.py` to recursively enforce `additionalProperties: false` and populate `required` lists.
- **Provider Fallback Ladder:** Added automatic fallback from `json_schema` to `json_object` when a provider returns HTTP 400 on strict schemas, with full error message reporting in `KeyPool`.
- **Per-Page Persistence & Caching:** Extraction results and observations are committed after each page completes. On retry, previously extracted pages are loaded directly from `extractions` cache, eliminating redundant LLM calls.
- **Frontend Polling & Actions:** Added `extracting` to polling loop, added status color for `extracting`, and enabled "Retry" action for `rate_limited` documents.
- **Startup Crash Recovery:** Marked orphaned in-flight documents (`extracting`, `normalizing`, `ocr`) as `failed` on server startup so users can retry them.

### Verification
| Check | Result | Notes |
|---|---|---|
| Backend Pytest Suite | Passed | 36/36 passed via `docker compose exec -T api pytest -v` |
| Flutter Analyzer | Passed | 0 issues found via `flutter analyze` |
| Flutter Test Suite | Passed | 4/4 passed via `flutter test` |
| Flutter Web Wasm Build | Passed | `flutter build web --wasm` compiled successfully |
| Live Provider Extraction | Passed | Verified live Groq API extraction with strict schema (15 observations on Page 1) |


## Task: Week 4 - Charts, Embeddings, Labs Screen, and Bake-offs

- **Date:** 2026-10-17
- **Status:** Completed

### Objective
Implement Week 4 deliverables according to `prototype-architecture.md`:
1. Local embedding engine (`EmbedEngine`) with SentenceTransformers supporting `multilingual-e5-small` and `bge-small-en-v1.5` mapped to 384-dimensional dense vectors.
2. Background embed worker (`embed_worker.py`) enqueued asynchronously on document confirmation, generating observation summary chunks and OCR page chunks.
3. Chart and test listing REST endpoints (`GET /api/v1/tests`, `GET /api/v1/charts/lab?test=<name>&from=&to=`).
4. Flutter Labs screen with search, customisable favorite trends section (defaults: HbA1c, Fasting Glucose, Hemoglobin, Total Cholesterol) persisted in `shared_preferences`, and all confirmed tests list.
5. Flutter Lab Detail screen with interactive `fl_chart` LineChart, shaded normal reference band, touch tooltips, time-range chips (3M / 6M / 1Y / ALL), and chronological record history table with direct links to source documents.
6. Embedding model bake-off evaluating Recall@5 on retrieval benchmarks (`eval/run_eval.py`, `eval/RESULTS.md`).

### Decisions Made
- **Asynchronous Embedding on Confirmation:** Document confirmation immediately updates status to `confirmed` and schedules the embedding worker as a FastAPI background task, ensuring responsive HTTP responses without blocking on model inference or download.
- **Model Aliases & Dimension Compatibility:** Mapped friendly names (`multilingual-e5-small` -> `intfloat/multilingual-e5-small`, `bge-small-en-v1.5` -> `BAAI/bge-small-en-v1.5`). Both produce 384-dimensional vectors conforming strictly to `chunks.embedding Vector(384)`.
- **Default & Persisted Favorites:** If the user has not toggled favorites, standard metabolic/hematology tests default to top cards. Toggling stars stores the set immediately in browser `shared_preferences`.
- **Null-Date Exclusion & Chronological Sorting:** Chart points with missing collection dates are excluded from the line chart series while all confirmed readings display chronologically.

### Changes Made

| File | Change | Reason |
|---|---|---|
| `api/app/pipeline/embed.py` | `EmbedEngine`, alias resolution, `observation_summary`, and singleton getter | Local vector embedding pipeline |
| `api/app/pipeline/embed_worker.py` | Background task embedding confirmed observations and OCR text into `chunks` | Asynchronous vector creation on confirm |
| `api/app/routers/documents.py` | Added `BackgroundTasks` to `confirm_document` enqueuing `embed_document` | Trigger embedding post-confirmation |
| `api/app/routers/charts.py` | Implemented `/tests` and `/charts/lab` endpoints | Feed lab test summaries and time-series data to UI |
| `api/app/schemas.py` | Added `LabTestSummary`, `ChartPoint`, `LabChartResponse` | Pydantic V2 response contracts |
| `api/app/main.py` | Mounted `charts.router` | Expose charts API routes |
| `app/lib/features/labs/lab_model.dart` | `LabTestSummary` model | Parse test listing and summary stats |
| `app/lib/features/labs/labs_controller.dart` | `labsControllerProvider` and `labFavouritesProvider` with SharedPreferences | State management for lab test list and favorites |
| `app/lib/features/labs/labs_screen.dart` | Search bar, favorite cards wrap, and full recorded test tiles | Labs overview UI |
| `app/lib/features/labs/lab_chart_controller.dart` | `ChartPoint`, `LabChartData`, time-range filter, `labChartProvider` | Lab trend time-series state |
| `app/lib/features/labs/lab_detail_screen.dart` | `fl_chart` LineChart with reference band, tooltips, and history table | Interactive lab detail view |
| `app/lib/features/navigation/app_router.dart` | Wired `/labs` and `/labs/:test` routes | Route navigation to labs screens |
| `eval/run_eval.py`, `eval/RESULTS.md` | Added `embed_bakeoff` mode and logged Recall@5 results | Embedding model bake-off |
| `api/tests/*` | `test_embed.py`, `test_embed_worker.py`, `test_charts_api.py` | Automated backend test coverage |
| `app/test/*` | `labs_screen_test.dart`, `lab_detail_screen_test.dart` | Automated frontend widget tests |

### Verification

| Check | Result | Notes |
|---|---|---|
| Backend Pytest Suite | Passed | 48/48 passed in 52.0s via `docker compose exec -T api pytest -v` |
| Flutter Analyzer | Passed | 0 issues found via `flutter analyze` |
| Flutter Test Suite | Passed | 8/8 passed via `flutter test` |
| Flutter Web Wasm Build | Passed | `flutter build web --wasm --release` succeeded in 38.2s |
| Embedding Bake-Off | Passed | `multilingual-e5-small`: 100.0% Recall@5; `bge-small-en-v1.5`: 90.0% Recall@5 |

### Final Outcome

- **Status:** Completed
- **Completed:** Week 4 milestone fully implemented, verified, and compiled.
- **Commit History:**
  - `4c4b7ac` — `feat(pipeline): add embed engine and observation summary formatter`
  - `49c161b` — `feat(pipeline): embed confirmed observations as chunks in background after confirm`
  - `f7f852f` — `feat(api): add /tests and /charts/lab endpoints for lab trend charting`
  - `ce005f9` — `feat(flutter): add Labs screen with favourites, test list, and navigation`
  - `bcd09ce` — `feat(flutter): add Lab Detail screen with fl_chart trend line, reference band, and history table`
  - `2aab442` — `eval: add embedding model bake-off and log Week 4 Recall@5 results`
  - `b78dc7d` — `fix(flutter): resolve analyzer warnings for super parameters and opacity`

**Week 4 milestone: COMPLETE ✅**

## Task: Canonical Lab Test Aliasing & Chart Grouping Fix

- **Date:** 2026-10-17
- **Status:** Completed

### Problem
- In `/api/v1/tests`, tests were grouped strictly by raw OCR string (`test_name`). Real reports extracted as `Hemoglobin (HB)` while synthetic test suite fixtures inserted raw `Hemoglobin` with `collected_at = None`.
- Users saw two separate entries (`Hemoglobin` with no dates, and `Hemoglobin (HB)` with actual dates). Tapping `Hemoglobin` yielded "No readings available".

### Solution
- Updated `list_available_tests` and `get_lab_chart` in `api/app/routers/charts.py` to alias-resolve against `lab_dictionary.json` via `_find_canonical_test_id`.
- Both `Hemoglobin` and `Hemoglobin (HB)` now merge under canonical key `hemoglobin` with title `Hemoglobin`.
- Historical points across both entries now render chronologically on the same trend line chart.

### Verification
- `GET /api/v1/charts/lab?test=Hemoglobin` returns 2 points (`2026-07-23` at 14.2 gm/dl, `2026-09-10` at 13.8 gm/dl) with ref band `13.0–17.0`.
- 6/6 tests passed in `test_charts_api.py`.

## Task: Remove Review Tab from Navigation

- **Date:** 2026-10-17
- **Status:** Completed

### Changes Made
| File | Change |
|---|---|
| `app/lib/features/navigation/app_router.dart` | Removed Review tab from BottomNavigationBar and NavigationRail; renumbered indexes for remaining tabs (Documents, Labs, Ask, Settings) |
| `architecture.md` | Removed Review tab from navigation and UI component listings |
| `prototype-architecture.md` | Removed Review tab from navigation and responsive layout table |

### Verification
| Check | Result |
|---|---|
| Flutter Analyze | ✅ 0 issues |
| Flutter Tests | ✅ 8/8 passed |
| Backend Pytest | ✅ 48/48 passed |
| WASM rebuild | ✅ Built successfully (37.6s) |
| Visual confirmation | ✅ Review tab no longer visible in browser |

**Note:** Source change alone isn't enough for WASM builds — must rebuild (`flutter build web --wasm`) and hard-refresh the browser.

## Task: Week 5 - Ask/RAG Feature, PWA Polish, Evaluation Bake-off, and Demo Script

- **Date:** 2026-10-18 / 2026-10-19
- **Status:** Completed

### Deliverables
1. **RAG Tools Layer (`api/app/rag/tools.py`)**: Read-only tools `list_tests`, `get_observations`, `get_latest_observations`, `search_documents` using RRF hybrid search.
2. **RAG Orchestrator (`api/app/rag/orchestrator.py`, `prompts.py`)**: Multi-turn tool calling with router prompt fallback and refusal for unanswerable queries.
3. **`POST /api/v1/ask` Endpoint (`api/app/routers/ask.py`)**: Mounted under `/api/v1/ask` with `AskResponse` and `CitationRef` schema.
4. **Flutter Ask Screen (`app/lib/features/ask/`)**: Interactive chat interface with `flutter_markdown_plus` rendering and citation chips linked to confirmed records.
5. **PWA Polish**: Offline connectivity banner, PWA install prompt banner, and service worker update listener.
6. **Lighthouse Audit**: 100/100 Accessibility, 100/100 SEO, 81/100 Best Practices.
7. **RAG Evaluation Bake-off**: 100% accuracy on valid QA pairs; detailed analysis and demo script in `eval/demo_script.md`.
8. **Final Verification**: 58/58 backend tests pass, 12/12 Flutter tests pass, 0 analyzer issues, Web Wasm compiled.

## Task: Multi-page Extraction & Review Page Navigation Fixes

- **Date:** 2026-10-19
- **Status:** Completed

### Problems
1. **Multi-page PDF stalls**: Ingestion sent successive requests without delays, tripping Groq's 7,000 ITPM rate limit on page 2.
2. **Missing extracted records**: OCR passed flat disconnected word boxes; LLM struggled to parse unassociated fragments and missed table rows.
3. **Review screen page navigation freeze**: In `ReviewScreen`, setting `_loadedPageNo = state.selectedPageNo` in build caused `_loadPageImage` to return immediately because it saw the page as already loaded, freezing the image pane on Page 1.
4. **Phantom test extraction**: Units and reference range fragments (e.g., `cells`, `cumm` from Platelet rows) were extracted as separate tests.

### Solutions
1. Added 5-second pacing delay between pages during extraction.
2. Grouped OCR bounding boxes by `row_id` into pipe-delimited table rows with explicit `[Line IDs: ...]` tags.
3. Fixed image loading state management by using `_lastRequestedPage` for scheduling guards, and added interactive page switcher buttons `< Page X of Y >` and page filter tabs (`All`, `Page 1`, `Page 2`, ...) in the review window.
4. Added negative constraints in `EXTRACTION_SYSTEM_PROMPT` and filter list in `normalize.py` to prevent units/headers from becoming observations.

### Verification
- Flutter analyze: 0 issues
- Flutter tests: 12/12 passed
- Backend tests: 58/58 passed
- Wasm build: compiled and served successfully

## Task: Purge and Remove Android Native Port Assets

- **Date:** 2026-10-23
- **Status:** Completed

### Decisions
- Suspended all Android native port initiatives per project direction.
- Removed isolated worktree, feature branch, and all associated native architecture/pipeline documents.

### Actions Taken
- Removed git worktree `/home/chandish/Documents/SwasthyaStats-android`.
- Deleted feature branch `feature/android-native-port` (and unmerged assets including `android-architecture.md`, `docs/superpowers/plans/2026-10-23-core-pipeline-dart.md`, and core Dart pipeline spikes).
- Pruned git worktree references.
- Verified `main` branch is clean with 0 uncommitted changes and no native port references.



---

## Task: PWA Enhancements — Offline Cache, Doctor Sort, Citations, Quick-Add

- **Date:** 2026-10-23
- **Status:** ✅ Completed (7 commits)

### Features Delivered

| # | Feature | Commit |
|---|---------|--------|
| 1 | Backend: doctor name extraction + document sort by doctor | `feat(api): extract doctor name and support document sorting by doctor` |
| 2 | Backend: manual observation endpoint + summary delta computation | `feat(api): add manual observation endpoint and compute summary deltas` |
| 3 | Flutter: LocalCacheService + offline banner (documents & labs) | `feat(app): add local cache service and offline results display` |
| 4 | Flutter: document auto-refresh (10s/3s polling) + doctor sort chip | `feat(app): add document auto-refresh, doctor name extraction display and sorting` |
| 5 | Flutter: review screen abnormal filter + inline quick-add test dialog | `feat(app): add abnormal filter and inline quick-add test dialog in review screen` |
| 6 | Flutter: labs abnormal filter + delta arrows (↑/↓) | `feat(app): add abnormal quick filter and summary delta indicators in labs` |
| 7 | Flutter: ask screen — starter chips, citation bottom sheets, clear history | `feat(app): add starter chips, citation bottom sheet, and clear chat history` |

### Decisions

- `sharedPreferencesProvider` / `localCacheServiceProvider` are nullable so tests that don't override them get `null` (no throw)
- All cache consumers use `cache?.method()` null-safe calls
- `DocumentsController` polls every 10 s (idle) / 3 s (in-progress); test overrides with `_EmptyDocumentsController` to avoid pending timer
- Android port entries removed/purged from docs

### Verification

| Check | Result |
|-------|--------|
| Backend `pytest tests/` | **60 passed**, 6 warnings |
| `flutter analyze` | **0 issues** |
| `flutter test` | **16/16 passed** |
| `flutter build web --wasm` | **✓ Built build/web** |


---

## Design Session: Multi-User Authentication

- **Date:** 2026-10-23
- **Branch:** `feat/auth-multi-user`
- **Status:** Design complete, awaiting plan

### Brainstorming Log (honest record of decisions made)

**What was asked:** Add user login with Google authentication for confidentiality and integrity.

**What was decided and why:**

1. **Dropped Google OAuth** — Google OAuth was the initial proposal, but the project's self-hosting goal means any external identity provider creates a hard dependency. If Google's OAuth endpoint is unreachable (no internet, Google outage), users can't log in. Argon2id + JWT is entirely self-contained and equally secure for this use case.

2. **Multi-user, not single-user** — The host runs the instance for friends and family. Each person gets their own account with strictly isolated data.

3. **Host cannot read guest data at rest** — This was the core privacy requirement surfaced during brainstorming. The design achieves this through per-user Fernet field encryption (derived from `SERVER_SECRET + user_id`). A database dump is unreadable without `SERVER_SECRET`.

4. **Honest limitations documented** — The following are explicitly NOT protected and are disclosed in the design document:
   - OCR and LLM processing window: host's server reads plaintext documents in memory during processing. Unavoidable with server-side AI.
   - `chunks.text` (RAG source text): stored plaintext because semantic search requires it.
   - A host with both DB access AND `SERVER_SECRET` (env var) can decrypt stored data.

5. **Per-user LLM API keys** — Each guest provides their own LLM API key. The host never pays for guest AI usage, and guest keys are encrypted with the guest's own derived key (host cannot see them).

6. **Self-hostable, zero internet required** — The only external call in the previous Google OAuth design was the identity verification at login. By switching to username/password + JWT, even that is eliminated. With Ollama as LLM provider, the system runs 100% offline.

7. **Admin-only user creation** — No self-registration. The host creates accounts for specific people. This keeps the guest list under the host's control.

8. **Clean slate migration** — Existing data is dropped. The current `Patient` model (single-tenant stub) is replaced by a proper `User` model.

### Design Document

`docs/superpowers/specs/2026-10-23-auth-multi-user-design.md`

### Key Security Properties

| Property | Achieved? |
|---|---|
| No external dependencies for auth | ✅ |
| Host cannot read guest data from DB dump | ✅ |
| Cross-user API access impossible | ✅ |
| Guest LLM keys hidden from host | ✅ |
| Host cannot read data during processing | ❌ (disclosed, unavoidable) |
| Chunk text hidden from host | ❌ (disclosed, needed for RAG) |

---

## Task: Docker backend and multi-user auth verification

- **Date:** 2026-10-24
- **Branch:** `chndsh-verify-auth-docker-tests`
- **Status:** Verification completed with one unresolved endpoint mismatch

### Verification

| Check | Result | Notes |
|---|---|---|
| Docker image build | Passed | `docker compose up -d --build` built the API image successfully |
| Isolated Docker stack | Passed | Started with host port publishing disabled because ports `5432` and `8000` were already occupied by another stack |
| Container health smoke test | Passed | `GET /health` returned `200` |
| Multi-user auth and isolation tests | Passed | `8 passed, 5 warnings` |
| Full backend test suite | Passed | `71 passed, 5 warnings` |
| Direct HTTP auth smoke flow | Passed | Health, login, `/auth/me`, bearer-authenticated documents, and unauthenticated rejection verified |
| Settings JWT migration | Failed | `/api/v1/settings` still requires the legacy `X-API-Key` header and rejects JWT-only requests |

### Remaining Risk

The multi-user design specifies bearer authentication for all existing endpoints, but the settings router still uses the legacy API-key dependency. This was observed during direct HTTP smoke testing and was not changed during this verification-only task.

---

## Task: Admin user management and temporary-password onboarding

- **Date:** 2026-10-24
- **Status:** Design and implementation plan complete

### Decisions

- Add `users.must_change_password`.
- Force password changes after user creation and admin password reset.
- Add admin UI for user listing, creation, password reset, and deletion.
- Add a guarded change-password screen before access to health-data routes.
- Invalidate existing refresh tokens after password changes and resets.
- Keep temporary passwords transient and never return them from list endpoints or log them.

### Documents

- Design: `docs/plans/2026-10-24-admin-user-management-design.md`
- Implementation plan: `docs/plans/2026-10-24-admin-user-management.md`
- Auth spec updated: `docs/superpowers/specs/2026-10-23-auth-multi-user-design.md`

### Final admin implementation verification

- **Date:** 2026-10-24
- **Branch:** `chndsh-admin-user-management`
- **Flutter tests:** Passed, `32 tests`
- **Flutter analyzer:** Passed, no issues
- **Flutter WASM web build:** Passed
- **Docker Compose config:** Passed
- **API image build:** Passed
- **Docker-backed backend suite:** Passed, `79 passed, 6 warnings`
- **Notes:** Tests ran in an isolated Compose project without published host ports because ports `5432` and `8000` were already allocated.
- **Additional hardening:** Admin create/reset and self-service password-change requests enforce an eight-character minimum at the API boundary.

## Task: Preserve OCR observations when page extraction is empty

- **Date:** 2026-10-25
- **Status:** Completed with legacy-test limitation

### Changes

- Added conservative OCR recovery when structured extraction returns no observations.
- Recovery accepts only explicit rows backed by known lab-test names and numeric or qualitative result values, preserving platelet OCR such as `4,04,000` without importing unsupported comments.
- Added an Admin Users back button.
- Added backend OCR and Flutter widget regression coverage.

### Verification

- Backend extraction regression: passed, `6 passed`.
- Flutter tests: passed, `36 tests`.
- Flutter analyzer: passed.
- Flutter WASM build: passed.
- Browser stack rebuilt from this branch on port `8001`; `/health`, `/`, admin login, and authenticated `/auth/users` returned `200`.
- Legacy `test_extraction_pipeline.py` remains blocked because its pre-existing fixture constructs the migrated `Patient` alias with removed `name`/legacy fields.

## Task: Clamp Groq extraction output tokens

- **Date:** 2026-10-25
- **Status:** Completed

### Changes

- Set the default configured maximum output tokens to `1000`.
- Clamp the effective Groq request token parameter to `1000` after extra parameters are merged, preventing provider rejection when stored settings still contain values such as `1973`.
- Added a request-payload regression test.

### Verification

- Focused backend LLM and extraction tests: passed, `11 passed`.
- Flutter tests: passed, `36 tests`.
- Flutter analyzer: passed.
- Flutter WASM build: passed.
- Browser stack rebuilt from `/home/chandish/copilot-worktrees/SwasthyaStats/chndsh-supreme-meme` and restarted as `chndsh-probable-robot` on port `8001`.
- Live `/health` and `/` returned `200`; Compose working directory and image were confirmed to use this worktree.

## Task: Chunk large-page extraction and route admin back navigation

- **Date:** 2026-10-25
- **Status:** Completed

### Changes

- Split page OCR into bounded six-line extraction requests and aggregate observations and metadata across all chunks, keeping each Groq request within the 1000-token output ceiling.
- Preserved the OCR recovery path for chunks whose model response is empty.
- Changed Admin Users back navigation to explicitly route to `/documents`.
- Added multi-row extraction and router-target regression tests.

### Verification

- Backend extraction and LLM regressions: passed, `12 passed`.
- Flutter full suite: passed, `37 tests`.
- Flutter analyzer: passed with no issues.
- Flutter WASM build: passed.

## Task: Restore single-request extraction and align with main branch

- **Date:** 2026-10-25
- **Status:** Completed

### Root Cause
- Artificial 6-line chunking (`MAX_EXTRACTION_LINES = 6`) divided OCR text into arbitrary slices, stripping table headers from subsequent chunks and truncating multi-line lab test entries, which caused missing tests.
- Sending 5-6 rapid requests per page in a synchronous loop rapidly consumed Groq RPM and free-tier OTPM rate limits, causing repeated 429 errors and pipeline abortion.
- Clamping Groq output tokens to 1000 in `client.py` artificially constrained valid model responses.

### Changes
- Restored `extract_page` in `api/app/pipeline/extract.py` to send complete page text in a single LLM request (1 page = 1 request), preserving full table headers and row context.
- Retained `recover_observations_from_ocr` as a full-page fallback only when LLM returns no observations.
- Removed artificial `GROQ_MAX_OUTPUT_TOKENS = 1000` clamp in `api/app/llm/client.py`.
- Restored `llm_max_output_tokens` default to 2000 in `api/app/schemas.py` and `api/app/services/settings.py`.
- Updated test suites in `api/tests/test_extract.py` and `api/tests/test_llm_client.py`.

### Verification
- Backend unit and integration test suite: passed, `80 passed, 5 warnings`.
- Flutter full test suite: passed, `37 tests passed`.
- Live API container restarted and verified healthy on port 8001.

## Task: Deduplicate lab test entries in tests/charts list

- **Date:** 2026-10-25
- **Status:** Completed

### Root Cause
- `_find_canonical_test_id` used exact lowercase string matching only. OCR variants with minor whitespace differences (`TOTAL LEUCOCYTE COUNT (TC)` vs `TOTAL LEUCOCYTE COUNT(TC)`) or OCR artifacts (`SGOTIAST` vs `SGOT/AST`) produced different keys and showed as separate entries.
- Many common CBC tests (PCV, MCV, MCH, MCHC, RBC, CRP, ESR) were absent from `lab_dictionary.json`, so any two OCR variants of the same test would each get their own raw-lowercase key.
- `charts.py` `get_lab_chart` only queried by `canonical_test_id` and exact string — not all aliases — so variant-named observations were excluded from chart data.

### Changes
| File | Change |
|---|---|
| `api/app/data/lab_dictionary.json` | Added 8 new canonical entries (PCV, MCV, MCH, MCHC, RBC, CRP, ESR, platelet_count). Expanded alias lists for WBC, SGPT, SGOT, sodium, potassium, calcium. |
| `api/data/lab_dictionary.json` | Synced copy of the above. |
| `api/app/pipeline/normalize.py` | Replaced `_find_canonical_test_id` with multi-step resolution: exact key → normalized name/alias (via new `normalize_test_name` helper) → base name without parens → substring match. `normalize_test_name` handles leuco→leuko, haemo→hemo, OCR artifacts, whitespace and parenthetical stripping. |
| `api/app/routers/charts.py` | `list_available_tests`: uses `normalize_test_name` as fallback key for unrecognized tests. `get_lab_chart`: OR filter now includes all aliases from the canonical entry, so all variant-named observations are returned. |
| `api/app/main.py` | Added startup backfill: re-resolves `canonical_test_id` for all `Observation` rows where it is `NULL`, runs once at startup inside `lifespan`. |
| `api/tests/test_normalize.py` | Added `test_find_canonical_test_id_matches_variations` covering 11 OCR/spacing variants. |
| `api/tests/test_charts_api.py` | Added `test_charts_merges_name_variations_into_single_entry` asserting `/api/v1/tests` returns 1 WBC entry for two differently-spelled observations. |

### Verification
- Backend test suite: passed, `82 passed, 5 warnings`.
- Live `/api/v1/tests`: `White Blood Cell Count` shows `count: 8` (all leucocyte variants merged); CRP `count: 2`; RBC `count: 2` — no duplicate entries.
- Container restarted; startup backfill ran on all pre-existing NULL `canonical_test_id` rows.
- Commit: `12150f5`

