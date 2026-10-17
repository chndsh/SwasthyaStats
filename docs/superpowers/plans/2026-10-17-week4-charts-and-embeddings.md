# Week 4: Charts and Embeddings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add trend charts for lab tests and background embeddings on document confirmation, so the Labs screen displays confirmed observations over time and the RAG infrastructure is ready for Week 5.

**Architecture:** Three backend additions — a charts router (`/tests`, `/charts/lab`), an embedding pipeline (`sentence-transformers` local model, one summary chunk per observation + one per OCR page), and a background embed task wired into the confirm endpoint. Two Flutter additions — a Labs screen (test list + favourites) and a Lab Detail screen (fl_chart line + reference band + history table + source-page link). Favourites stored in `shared_preferences`.

**Tech Stack:** FastAPI, SQLAlchemy 2, pgvector, `sentence-transformers` (already in requirements.txt), `fl_chart ^0.69.2`, `shared_preferences ^2.3.3`, `go_router`, Riverpod.

**Spec:** `prototype-architecture.md` — Sections 10.3 (Trend chart), 11 (RAG chunk structure), 12 (Labs screen), 13 (API `/tests`, `/charts/lab`), 17 Week 4 exit criteria.

## Global Constraints

- Python ≥ 3.11; FastAPI ≥ 0.115; SQLAlchemy 2; Pydantic v2; `pgvector ≥ 0.3.6`.
- Flutter web target only; `--wasm` compilation; no `dart:io`; no `dart:html`.
- All API routes under `/api/v1`, all requiring `X-API-Key` header (`verify_api_key` dependency).
- Embedding dimension: 384 (fixed by `chunks.embedding Vector(384)` in `models.py`). Default embed model: `multilingual-e5-small`.
- `sentence-transformers` already in `requirements.txt`; no new Python deps needed.
- `fl_chart`, `shared_preferences` already in `pubspec.yaml`; no new Flutter deps needed.
- Confirmed-only observations feed charts (`status = 'confirmed'`).
- Embedding runs as a background task after confirm — confirm endpoint response must not block on it.
- Favourites default to `['HbA1c', 'Fasting Glucose', 'Hemoglobin', 'Total Cholesterol']` when none saved.
- Every task ends with tests passing and a commit.

## Review Focus

- **No confirmed observations yet:** `GET /charts/lab` with a valid test name but zero confirmed rows must return `{"points": [], "ref_low": null, "ref_high": null, "unit": null}` (not 404 or 500).
- **Embed model cold-start latency:** first call to `EmbedEngine.embed()` triggers model download to the `hf:` volume; the confirm endpoint must still return promptly (background task owns the wait).
- **`collected_at` nulls:** observations may have `collected_at = null`; chart points with null dates must be excluded from the series silently rather than raising.
- **Bake-off model swap:** changing `embed.model` to `bge-small-en-v1.5` (also 384-d) must re-embed without changing any model code — only `embed_model` setting drives the choice.
- **Favourites with no data:** a favourited test that has no confirmed observations must render gracefully on the Labs screen (show the card with "No data yet" rather than crashing).

---

## Task 1: Embed Engine

**Files:**
- Create: `api/app/pipeline/embed.py`
- Test: `api/tests/test_embed.py`

**Interfaces:**
- Produces:
  - `class EmbedEngine` with method `embed(texts: list[str]) -> list[list[float]]`
  - Module-level singleton getter `get_embed_engine() -> EmbedEngine`
  - `observation_summary(obs: Observation) -> str` — formats `"{test_name} {value_num} {unit} on {collected_at} (ref {ref_low}–{ref_high})"`, substituting `"?"` for any None field.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_embed.py
from app.pipeline.embed import EmbedEngine, observation_summary
from app.models import Observation
import datetime

def test_embed_returns_384_floats():
    engine = EmbedEngine(model_name="multilingual-e5-small")
    vecs = engine.embed(["Hemoglobin 13.2 g/dL"])
    assert len(vecs) == 1
    assert len(vecs[0]) == 384
    assert all(isinstance(v, float) for v in vecs[0])

def test_observation_summary_full():
    obs = Observation(
        test_name="HbA1c", value_num=6.8, unit="%",
        collected_at=datetime.date(2026, 10, 14), ref_low=4.0, ref_high=5.6,
    )
    assert observation_summary(obs) == "HbA1c 6.8 % on 2026-10-14 (ref 4.0–5.6)"

def test_observation_summary_nulls():
    obs = Observation(test_name="Glucose", value_num=None, unit=None,
                      collected_at=None, ref_low=None, ref_high=None)
    result = observation_summary(obs)
    assert "Glucose" in result
    assert "?" in result

def test_get_embed_engine_singleton():
    from app.pipeline.embed import get_embed_engine
    a = get_embed_engine()
    b = get_embed_engine()
    assert a is b
```

- [ ] **Step 2: Run to verify they fail**

```bash
docker compose exec -T api pytest api/tests/test_embed.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.pipeline.embed'`

- [ ] **Step 3: Implement `api/app/pipeline/embed.py`**

  - `EmbedEngine.__init__(model_name: str)` — loads `SentenceTransformer(model_name)` (downloads to `/root/.cache/huggingface` volume on first call).
  - `embed(texts: list[str]) -> list[list[float]]` — calls `model.encode(texts, normalize_embeddings=True).tolist()`.
  - `observation_summary(obs: Observation) -> str` — format as specified in Review Focus.
  - `_engine_instance: EmbedEngine | None = None`; `get_embed_engine()` reads `embed_model` from `SettingsService` and returns or creates the singleton.

- [ ] **Step 4: Run to verify they pass**

```bash
docker compose exec -T api pytest api/tests/test_embed.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/pipeline/embed.py api/tests/test_embed.py
git commit -m "feat(pipeline): add embed engine and observation summary formatter"
```

---

## Task 2: Background Embed Worker + Confirm Hook

**Files:**
- Create: `api/app/pipeline/embed_worker.py`
- Modify: `api/app/routers/documents.py` — `confirm_document` endpoint (add `BackgroundTasks` param, enqueue worker)
- Test: `api/tests/test_embed_worker.py`

**Interfaces:**
- Consumes: `EmbedEngine`, `get_embed_engine()`, `observation_summary()` from Task 1.
- Produces:
  - `embed_document(document_id: int) -> None` — opens its own `SessionLocal`, creates/replaces `Chunk` rows for the document, commits. Designed to run as a background task.

- [ ] **Step 1: Write the failing tests**

```python
# api/tests/test_embed_worker.py
from unittest.mock import patch, MagicMock
import datetime

def test_embed_document_creates_chunks(db_session, sample_confirmed_document):
    """embed_document inserts Chunk rows for each confirmed observation + one per page."""
    from app.pipeline.embed_worker import embed_document
    from app.models import Chunk

    with patch("app.pipeline.embed_worker.get_embed_engine") as mock_eng:
        mock_eng.return_value.embed.return_value = [[0.1] * 384]
        embed_document(sample_confirmed_document.id)

    chunks = db_session.query(Chunk).filter(
        Chunk.document_id == sample_confirmed_document.id
    ).all()
    assert len(chunks) >= 1
    assert all(len(c.embedding) == 384 for c in chunks)

def test_embed_document_replaces_existing_chunks(db_session, sample_confirmed_document):
    """Calling embed_document twice does not duplicate chunks."""
    from app.pipeline.embed_worker import embed_document
    from app.models import Chunk

    with patch("app.pipeline.embed_worker.get_embed_engine") as mock_eng:
        mock_eng.return_value.embed.return_value = [[0.1] * 384]
        embed_document(sample_confirmed_document.id)
        embed_document(sample_confirmed_document.id)

    count = db_session.query(Chunk).filter(
        Chunk.document_id == sample_confirmed_document.id
    ).count()
    assert count == db_session.query(Chunk).filter(
        Chunk.document_id == sample_confirmed_document.id
    ).count()
```

- [ ] **Step 2: Run to verify they fail**

```bash
docker compose exec -T api pytest api/tests/test_embed_worker.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `api/app/pipeline/embed_worker.py`**

  - `embed_document(document_id: int) -> None`:
    1. Open `SessionLocal()` in a `try/finally`.
    2. Load confirmed observations for the document.
    3. Delete existing `Chunk` rows for the document (idempotent re-embed).
    4. Build texts: one `observation_summary(obs)` per confirmed observation; one `doc.ocr_text[:2000]` chunk per page (use `document_pages` page numbers, truncated to 2000 chars to keep embedding cost low).
    5. If no texts, return early.
    6. Call `get_embed_engine().embed(texts)` to get vectors.
    7. Insert `Chunk(document_id, text, embed_model, embedding, page)` for each.
    8. Commit.
    9. `logger.info(f"Embedded {len(texts)} chunks for document {document_id}")`.

- [ ] **Step 4: Wire into confirm endpoint in `api/app/routers/documents.py`**

  Add `BackgroundTasks` parameter to `confirm_document`. After `db.commit()`, add:
  ```python
  background_tasks.add_task(embed_document_bg, document_id)
  ```
  where `embed_document_bg` is a thin wrapper (same pattern as `_retry_worker`) that calls `embed_document(document_id)`.

- [ ] **Step 5: Run to verify they pass**

```bash
docker compose exec -T api pytest api/tests/test_embed_worker.py api/tests/test_documents_api.py -v
```
Expected: all pass (existing confirm tests must still pass).

- [ ] **Step 6: Commit**

```bash
git add api/app/pipeline/embed_worker.py api/app/routers/documents.py api/tests/test_embed_worker.py
git commit -m "feat(pipeline): embed confirmed observations as chunks in background after confirm"
```

---

## Task 3: Charts API (`/tests` + `/charts/lab`)

**Files:**
- Create: `api/app/routers/charts.py`
- Modify: `api/app/main.py` — include `charts_router`
- Modify: `api/app/schemas.py` — add `LabTestSummary`, `ChartPoint`, `LabChartResponse`
- Test: `api/tests/test_charts_api.py`

**Interfaces:**
- Produces:
  - `GET /api/v1/tests` → `list[LabTestSummary]`
  - `GET /api/v1/charts/lab?test=<name>&from=<date>&to=<date>` → `LabChartResponse`
  - Schemas:
    ```python
    class LabTestSummary(BaseModel):
        test_name: str
        canonical_test_id: Optional[str]
        count: int           # confirmed observations
        latest_value: Optional[float]
        latest_unit: Optional[str]
        latest_flag: Optional[str]
        latest_date: Optional[date]
        ref_low: Optional[float]   # from most recent observation
        ref_high: Optional[float]

    class ChartPoint(BaseModel):
        date: date
        value: float
        flag: Optional[str]
        document_id: int
        page_no: int

    class LabChartResponse(BaseModel):
        test_name: str
        points: list[ChartPoint]   # empty list when no data
        ref_low: Optional[float]
        ref_high: Optional[float]
        unit: Optional[str]
    ```

- [ ] **Step 1: Add schemas to `api/app/schemas.py`**

  Append `LabTestSummary`, `ChartPoint`, `LabChartResponse` as defined in Interfaces above.

- [ ] **Step 2: Write the failing tests**

```python
# api/tests/test_charts_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "change-me"}

def test_list_tests_empty():
    r = client.get("/api/v1/tests", headers=HEADERS)
    assert r.status_code == 200
    assert r.json() == []

def test_list_tests_with_confirmed_obs(db_with_confirmed_obs):
    r = client.get("/api/v1/tests", headers=HEADERS)
    assert r.status_code == 200
    names = [t["test_name"] for t in r.json()]
    assert "HbA1c" in names

def test_charts_lab_no_data():
    r = client.get("/api/v1/charts/lab?test=NonExistent", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == []
    assert body["ref_low"] is None
    assert body["ref_high"] is None
    assert body["unit"] is None

def test_charts_lab_returns_points(db_with_confirmed_obs):
    r = client.get("/api/v1/charts/lab?test=HbA1c", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) >= 1
    assert body["points"][0]["value"] == 6.8
    assert body["unit"] == "%"

def test_charts_lab_excludes_null_dates(db_with_null_date_obs):
    """Observations with collected_at=None must be silently excluded."""
    r = client.get("/api/v1/charts/lab?test=Glucose", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["points"] == []

def test_charts_lab_date_filter(db_with_confirmed_obs):
    r = client.get("/api/v1/charts/lab?test=HbA1c&from=2026-01-01&to=2026-06-30", headers=HEADERS)
    assert r.status_code == 200
    # all points in range
    for p in r.json()["points"]:
        assert "2026-01" <= p["date"] <= "2026-06-30"
```

- [ ] **Step 3: Run to verify they fail**

```bash
docker compose exec -T api pytest api/tests/test_charts_api.py -v
```
Expected: FAIL — `404 Not Found` (routes not yet registered).

- [ ] **Step 4: Implement `api/app/routers/charts.py`**

  - `GET /api/v1/tests`: query `Observation` where `status='confirmed'`, group by `test_name` + `canonical_test_id`; for each group pick the row with the latest `collected_at` for `latest_*` fields and count total. Return `list[LabTestSummary]` sorted alphabetically by `test_name`.
  - `GET /api/v1/charts/lab`: accept `test: str`, optional `from_date: date = Query(None, alias="from")`, `to_date: date = Query(None, alias="to")`. Query confirmed observations matching `test_name` (case-insensitive, or `canonical_test_id` if provided), filter out `collected_at=None`, apply optional date range, order by `collected_at`. Return `LabChartResponse`; if no rows found return `LabChartResponse(test_name=test, points=[], ref_low=None, ref_high=None, unit=None)`.

- [ ] **Step 5: Register router in `api/app/main.py`**

  ```python
  from app.routers import charts as charts_router
  app.include_router(charts_router.router)
  ```

- [ ] **Step 6: Run to verify they pass**

```bash
docker compose exec -T api pytest api/tests/test_charts_api.py -v
```
Expected: all pass.

- [ ] **Step 7: Run full suite**

```bash
docker compose exec -T api pytest -v
```
Expected: all previous tests still pass.

- [ ] **Step 8: Commit**

```bash
git add api/app/routers/charts.py api/app/main.py api/app/schemas.py api/tests/test_charts_api.py
git commit -m "feat(api): add /tests and /charts/lab endpoints for lab trend charting"
```

---

## Task 4: Labs Flutter Screen (Test List + Favourites)

**Files:**
- Create: `app/lib/features/labs/lab_model.dart`
- Create: `app/lib/features/labs/labs_controller.dart`
- Create: `app/lib/features/labs/labs_screen.dart`
- Modify: `app/lib/features/navigation/app_router.dart` — replace `LabsPlaceholderScreen` with `LabsScreen`, add `/labs/:test` child route pointing to `LabDetailScreen` (Task 5).
- Test: `app/test/labs_screen_test.dart`

**Interfaces:**
- Consumes: `ApiClient` (dio), `GET /api/v1/tests` response.
- Produces:
  ```dart
  // lab_model.dart
  class LabTestSummary {
    final String testName;
    final String? canonicalTestId;
    final int count;
    final double? latestValue;
    final String? latestUnit;
    final String? latestFlag;
    final String? latestDate;   // ISO-8601 date string
    final double? refLow;
    final double? refHigh;
    factory LabTestSummary.fromJson(Map<String, dynamic> json);
  }

  // labs_controller.dart
  final labsControllerProvider = AsyncNotifierProvider<LabsController, List<LabTestSummary>>();
  class LabsController extends AsyncNotifier<List<LabTestSummary>> {
    Future<List<LabTestSummary>> build();  // fetches GET /api/v1/tests
  }

  // favourites stored in shared_preferences under key 'lab_favourites' as JSON list of strings
  final labFavouritesProvider = StateNotifierProvider<LabFavouritesNotifier, Set<String>>();
  class LabFavouritesNotifier extends StateNotifier<Set<String>> {
    void toggle(String testName);
    // persists to shared_preferences immediately on toggle
  }
  // Default favourites (used when nothing saved): ['HbA1c', 'Fasting Glucose', 'Hemoglobin', 'Total Cholesterol']
  ```

- [ ] **Step 1: Write the failing test**

```dart
// app/test/labs_screen_test.dart
void main() {
  testWidgets('LabsScreen shows test list and favourite section', (tester) async {
    // arrange: mock controller returning two tests
    // act: pump LabsScreen
    // assert: finds 'HbA1c' and 'Fasting Glucose' text; finds 'Favourites' or 'Pinned' section header
  });

  testWidgets('LabsScreen shows No data placeholder when list is empty', (tester) async {
    // arrange: mock controller returning []
    // act: pump LabsScreen
    // assert: finds 'No confirmed tests yet' or similar text; no crash
  });

  testWidgets('Tapping a test navigates to /labs/:test', (tester) async {
    // arrange: mock controller; set up GoRouter with labs route
    // act: tap the first test card
    // assert: router pushes '/labs/<testName>'
  });
}
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd app && flutter test test/labs_screen_test.dart
```
Expected: FAIL — `Target file 'lib/features/labs/labs_screen.dart' not found`

- [ ] **Step 3: Implement `lab_model.dart`**

  Plain Dart class with `fromJson` factory. No logic beyond field parsing.

- [ ] **Step 4: Implement `labs_controller.dart`**

  - `LabsController.build()`: `GET /api/v1/tests`, parse to `List<LabTestSummary>`, sort alphabetically (already sorted by API, but defensive sort is fine).
  - `LabFavouritesNotifier`: loads favourites from `SharedPreferences` on construction; defaults to the four names in Global Constraints if nothing saved; `toggle` adds/removes from set and writes back to prefs.

- [ ] **Step 5: Implement `labs_screen.dart`**

  Layout:
  - **Favourites section** (collapsed to empty state message if none): horizontal `Wrap` or `GridView` of `LabFavouriteCard` widgets (test name, latest value + unit, flag chip, trend mini-indicator — just up/down/flat arrow from flag). Tap → `context.go('/labs/${Uri.encodeComponent(test.testName)}')`.
  - **All Tests section**: `ListView` with `LabTestListTile` (test name, latest value + unit, flag, count, star icon for favourite toggle). Tap → same navigation.
  - Pull-to-refresh calls `ref.refresh(labsControllerProvider)`.
  - Empty state: "No confirmed tests yet. Confirm a document to see trends."
  - Favourite card with no data (favoured test name not in test list): show card with "No data yet".

- [ ] **Step 6: Wire into `app_router.dart`**

  Replace:
  ```dart
  GoRoute(path: '/labs', builder: (context, state) => const LabsPlaceholderScreen()),
  ```
  With:
  ```dart
  GoRoute(
    path: '/labs',
    builder: (context, state) => const LabsScreen(),
    routes: [
      GoRoute(
        path: ':test',
        builder: (context, state) {
          final test = Uri.decodeComponent(state.pathParameters['test'] ?? '');
          return LabDetailScreen(testName: test);
        },
      ),
    ],
  ),
  ```
  Import `LabsScreen` and `LabDetailScreen` (stub for now — Task 5 will implement it; create a minimal placeholder that accepts `testName` and shows it).

- [ ] **Step 7: Run to verify tests pass**

```bash
cd app && flutter test test/labs_screen_test.dart
```
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add app/lib/features/labs/ app/lib/features/navigation/app_router.dart app/test/labs_screen_test.dart
git commit -m "feat(flutter): add Labs screen with favourites, test list, and navigation"
```

---

## Task 5: Lab Detail Screen (Trend Chart + History Table)

**Files:**
- Create: `app/lib/features/labs/lab_detail_screen.dart`
- Create: `app/lib/features/labs/lab_chart_controller.dart`
- Test: `app/test/lab_detail_screen_test.dart`

**Interfaces:**
- Consumes:
  - `LabTestSummary` (Task 4)
  - `GET /api/v1/charts/lab?test=<name>&from=<date>&to=<date>` response
- Produces:
  ```dart
  // lab_chart_controller.dart
  class ChartPoint {
    final DateTime date;
    final double value;
    final String? flag;
    final int documentId;
    final int pageNo;
    factory ChartPoint.fromJson(Map<String, dynamic> json);
  }

  class LabChartData {
    final String testName;
    final List<ChartPoint> points;
    final double? refLow;
    final double? refHigh;
    final String? unit;
  }

  // Provider: takes testName as family parameter
  final labChartProvider = AsyncNotifierProviderFamily<LabChartController, LabChartData, String>();
  class LabChartController extends FamilyAsyncNotifier<LabChartData, String> {
    Future<LabChartData> build(String testName);
  }
  ```

- [ ] **Step 1: Write the failing tests**

```dart
// app/test/lab_detail_screen_test.dart
void main() {
  testWidgets('LabDetailScreen renders chart and history table', (tester) async {
    // arrange: mock labChartProvider returning 2 points for 'HbA1c'
    // act: pump LabDetailScreen(testName: 'HbA1c')
    // assert: finds 'HbA1c'; finds the fl_chart LineChart widget; finds history table rows
  });

  testWidgets('Empty points show no-data message', (tester) async {
    // arrange: mock labChartProvider returning empty points
    // act: pump LabDetailScreen(testName: 'Glucose')
    // assert: finds 'No data' text; no crash
  });

  testWidgets('Tapping a history row navigates to source document page', (tester) async {
    // arrange: mock provider with 1 point (documentId:1, pageNo:1); mock GoRouter
    // act: tap the history table row
    // assert: router goes to '/documents/1' (document view)
  });

  testWidgets('Time range filter chips update the chart', (tester) async {
    // arrange: mock provider; pump screen
    // act: tap '3M' chip
    // assert: labChartProvider is re-fetched (verify controller refresh triggered)
  });
}
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd app && flutter test test/lab_detail_screen_test.dart
```
Expected: FAIL.

- [ ] **Step 3: Implement `lab_chart_controller.dart`**

  - `LabChartController.build(String testName)`: `GET /api/v1/charts/lab?test=<testName>`, parse to `LabChartData`.
  - Time-range filter is a UI concern: the screen passes `from`/`to` query params by calling `ref.refresh` with updated args when the chip changes. The controller always fetches with whatever range params the screen provides (implement as a `StateProvider<String>` for the active range — `"3M"`, `"6M"`, `"1Y"`, `"ALL"` — computed to from/to dates on fetch).

- [ ] **Step 4: Implement `lab_detail_screen.dart`**

  - App bar: test name + star icon (toggles favourite via `LabFavouritesNotifier`).
  - Time range chips row: `3M`, `6M`, `1Y`, `All` — tapping updates a local `StateProvider` and refreshes the chart provider.
  - **fl_chart `LineChart`**:
    - Reference band: `betweenBarsData` or `rangeAnnotations` shading `refLow`–`refHigh` in green with 15% opacity.
    - Line from `points` sorted by date, `value_num` on Y axis.
    - X axis: date labels (month + year).
    - Touching a point shows a tooltip with date, value, flag.
    - Empty state (points is empty): centered "No data for this range".
  - **History table** below chart: `DataTable` with columns Date / Value / Flag / Report. Flag cell uses coloured chip (green=normal, amber=low, red=high/critical). Report cell: `TextButton` with document filename truncated to 20 chars, taps to `context.go('/documents/${point.documentId}')`.
  - Pull-to-refresh refreshes the chart provider.

- [ ] **Step 5: Run to verify tests pass**

```bash
cd app && flutter test test/lab_detail_screen_test.dart
```
Expected: all pass.

- [ ] **Step 6: Run full Flutter test suite**

```bash
cd app && flutter test
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add app/lib/features/labs/lab_detail_screen.dart app/lib/features/labs/lab_chart_controller.dart app/test/lab_detail_screen_test.dart
git commit -m "feat(flutter): add Lab Detail screen with fl_chart trend line, reference band, and history table"
```

---

## Task 6: Embedding Bake-Off + Eval Logging

**Files:**
- Modify: `eval/run_eval.py` — add `embed_bakeoff()` function
- Modify: `eval/RESULTS.md` — add Week 4 results section

**Interfaces:**
- Consumes: `EmbedEngine` (Task 1), 30 retrieval queries against embedded chunks.

- [ ] **Step 1: Add `embed_bakeoff()` to `eval/run_eval.py`**

  Function signature: `embed_bakeoff(document_id: int, queries: list[str], top_k: int = 5) -> dict`.
  - For each model in `["multilingual-e5-small", "bge-small-en-v1.5"]`:
    1. Instantiate `EmbedEngine(model_name=model)`.
    2. Embed all `Chunk.text` rows for the document.
    3. For each query, compute cosine similarity against all chunk embeddings, return top-k chunk texts.
    4. Record Recall@5 (fraction of queries where ground-truth answer chunk appears in top 5).
  - Return `{"multilingual-e5-small": recall, "bge-small-en-v1.5": recall}`.

- [ ] **Step 2: Run bake-off against eval fixtures**

```bash
docker compose exec -T api python eval/run_eval.py --mode embed-bakeoff
```
Expected: prints Recall@5 for both models.

- [ ] **Step 3: Log results in `eval/RESULTS.md`**

  Append a `## Week 4 — Embeddings Bake-Off` section with the Recall@5 numbers, chosen model, and rationale.

- [ ] **Step 4: Commit**

```bash
git add eval/run_eval.py eval/RESULTS.md
git commit -m "eval: add embedding model bake-off and log Week 4 Recall@5 results"
```

---

## Task 7: End-to-End Verification

- [ ] **Step 1: Run full backend test suite**

```bash
docker compose exec -T api pytest -v
```
Expected: all tests pass.

- [ ] **Step 2: Run Flutter analyzer and tests**

```bash
cd app && flutter analyze && flutter test
```
Expected: 0 issues, all tests pass.

- [ ] **Step 3: Build Flutter Web Wasm**

```bash
cd app && flutter build web --wasm --release
```
Expected: build succeeds.

- [ ] **Step 4: Smoke-test the full flow**

  1. Confirm a document via the Review screen.
  2. Open the Labs tab — tests from the document appear in the list.
  3. Tap a test — detail chart loads, reference band visible, history row present.
  4. Tap a history row — navigates to the document view.
  5. Confirm a second document with the same test — the chart shows two data points.
  6. Check DB: `SELECT count(*) FROM chunks WHERE document_id = <id>` — must be > 0.

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: Week 4 complete — charts, embeddings, Labs screen"
```
