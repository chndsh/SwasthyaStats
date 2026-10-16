# Week 3: Extraction and Review — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Week 2 pipeline (OCR → `needs_review`) to include PII redaction, structured LLM extraction, grounding/normalization/confidence scoring, rate-limit handling, review and confirm REST endpoints, a Flutter review screen, and bake-off evaluation.

**Architecture:** After OCR, the background pipeline calls `redact.py` → `extract.py` (one sequential LLM call per page) → `normalize.py` (grounding + dictionary + confidence) → writes `Extraction` + pending `Observation` rows → sets `needs_review`. The Flutter review screen polls for status then renders the page image beside editable observation rows, low-confidence first, with a single "Confirm all" action.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL (pgvector), `httpx`, `tenacity`, Pydantic v2, Python `re` (redaction), Flutter Web (Wasm), `fl_chart` (deferred), `flutter_riverpod`, pytest, `respx`.

**Spec:** `prototype-architecture.md` §§8, 10, 12, 13, 17 (Week 3)

## Global Constraints

- Sequential LLM calls per page — no concurrency semaphore this week (my call; defer to Week 4).
- Extraction calls use `json_schema` (structured output); never combine with `tools` (existing client enforces this).
- No value is auto-accepted; confidence drives review *highlighting* only.
- Images never leave the machine; only redacted OCR text goes to the LLM.
- All tables (`extractions`, `observations`) were created in Week 1 Alembic baseline — **no new migration needed**.
- `lab_dictionary.json` already exists at `api/data/lab_dictionary.json`; extend it as needed, never replace.
- `process_document_background` in `api/app/services/documents.py` is the pipeline entry point — extend it in place.

## Review Focus

- **Hallucinated numeric value:** LLM returns a value whose exact string doesn't appear in the referenced OCR lines → grounding check must flag it (reject from `observations`, set grounding_passed=False).
- **Multiple keys all rate-limited:** `OpenAICompatClient.chat()` raises `RuntimeError("All configured API keys are currently exhausted…")` — pipeline must catch this and set `status=rate_limited`, not `failed`.
- **Malformed LLM JSON with retry exhausted:** all structured-mode fallbacks fail → document must land at `failed` with a manual-entry hint, not crash silently.
- **`PATCH /observations/{id}` on a confirmed document:** editing should be blocked with `409 Conflict`.
- **OCR line `conf` is the mean of merged cells:** confidence scoring must not over-penalize merged cells; use the raw line-level conf stored in `ocr_lines` JSONB.

---

## Task 1: PII Redaction

**Files:**
- Create: `api/app/pipeline/redact.py`
- Test: `api/tests/test_redact.py`

**Interfaces:**
- Produces: `redact_text(text: str, patient_name: str | None = None) -> str`

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_redact.py
from app.pipeline.redact import redact_text

def test_patient_name_masked():
    result = redact_text("Patient: Ram Bahadur\nHemoglobin 13.2", patient_name="Ram Bahadur")
    assert "[PATIENT]" in result
    assert "Hemoglobin" in result   # medical term preserved

def test_standard_pii_masked():
    result = redact_text("DOB: 1985-03-14, Phone: 9841012345, Email: user@example.com")
    assert "1985-03-14" not in result
    assert "9841012345" not in result
    assert "user@example.com" not in result

def test_lab_values_not_masked():
    text = "Glucose | 95 | mg/dL | 70–110"
    result = redact_text(text)
    assert result == text  # nothing masked
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_redact.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.redact'`

- [ ] **Step 3: Implement `redact_text` in `api/app/pipeline/redact.py`**

Regexes to apply in order (replace with placeholder):
1. Patient name (case-insensitive word boundary match on `patient_name`, if provided) → `[PATIENT]`
2. Lines starting with `Name:` or `Patient Name:` → keep the label, replace value with `[PATIENT]`
3. DOB / Date of Birth lines → `[DOB]`
4. Phone numbers (10-digit runs, +91 prefix variants) → `[PHONE]`
5. Email addresses → `[EMAIL]`
6. Address-like patterns (P.O. Box, Ward No., street suffixes) → `[ADDRESS]`
7. National ID patterns (Citizenship No., Passport No. followed by alphanumeric) → `[ID]`

Keep: test names, values, units, ranges, collection dates (standalone dates not on PII header lines), lab names.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_redact.py -v`
Expected: PASS with 3 passed

- [ ] **Step 5: Commit**

```bash
git add api/app/pipeline/redact.py api/tests/test_redact.py
git commit -m "feat(pipeline): add PII redaction for OCR text before LLM extraction"
```

---

## Task 2: Extraction Schemas and LLM Prompt

**Files:**
- Create: `api/app/pipeline/extract.py`
- Test: `api/tests/test_extract.py`

**Interfaces:**
- Consumes: `OpenAICompatClient` from `api/app/llm/client.py` (`.chat(messages, purpose="extract", json_schema=...)`)
- Produces:
  ```python
  class LabObservationRaw(BaseModel):
      test_name: str
      value: float | None
      value_text: str | None
      unit: str | None
      ref_low: float | None
      ref_high: float | None
      flag: Literal["low", "normal", "high", "critical"] | None
      line_ids: list[int]        # OCR line IDs this came from

  class LabReportRaw(BaseModel):
      lab_name: str | None
      report_date: date | None
      observations: list[LabObservationRaw]

  class ExtractionFailed(Exception): pass

  def extract_page(
      redacted_text: str,
      ocr_line_ids: list[int],
      client: OpenAICompatClient,
      prompt_version: str = "v1",
  ) -> LabReportRaw
  ```

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_extract.py
import json
from unittest.mock import MagicMock
from datetime import date
from app.pipeline.extract import extract_page, LabReportRaw, ExtractionFailed
from app.llm.client import LlmResponse

def _make_client(content: str) -> MagicMock:
    client = MagicMock()
    client.chat.return_value = LlmResponse(
        content=content, prompt_tokens=100, completion_tokens=50,
        latency_ms=200, model_used="test-model", key_label="k1",
    )
    return client

def test_extract_page_happy_path():
    payload = {
        "lab_name": "City Lab", "report_date": "2026-10-01",
        "observations": [{
            "test_name": "Hemoglobin", "value": 13.2, "value_text": None,
            "unit": "g/dL", "ref_low": 12.0, "ref_high": 16.0,
            "flag": "normal", "line_ids": [1, 2],
        }]
    }
    client = _make_client(json.dumps(payload))
    result = extract_page("Hemoglobin | 13.2 | g/dL", ocr_line_ids=[1, 2], client=client)
    assert isinstance(result, LabReportRaw)
    assert len(result.observations) == 1
    assert result.observations[0].test_name == "Hemoglobin"

def test_extract_page_raises_on_all_failures():
    client = MagicMock()
    client.chat.side_effect = RuntimeError("All configured API keys are currently exhausted")
    try:
        extract_page("some text", ocr_line_ids=[1], client=client)
        assert False, "Should have raised"
    except RuntimeError:
        pass  # Expected — caller catches this to set rate_limited
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.extract'`

- [ ] **Step 3: Implement `extract_page` in `api/app/pipeline/extract.py`**

Prompt template (system):
```
You extract lab test results from OCR text of a medical lab report.
Return only valid JSON matching the schema. Each observation must reference
the line_ids it was extracted from. Do not invent values not present in the text.
```

User message: the `redacted_text`.

Fallback ladder on `json.JSONDecodeError` or schema validation error:
1. Retry once with the same structured mode.
2. Retry with `json_object` mode (override via `settings.llm_structured_mode = "json_object"`).
3. Raise `ExtractionFailed("Could not parse extraction response after retries")`.

Re-raise `RuntimeError` (all keys exhausted) unchanged — the pipeline catches it to set `rate_limited`.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_extract.py -v`
Expected: PASS with 2 passed

- [ ] **Step 5: Commit**

```bash
git add api/app/pipeline/extract.py api/tests/test_extract.py
git commit -m "feat(pipeline): add LLM extraction schemas, prompt, and fallback ladder"
```

---

## Task 3: Grounding Check, Normalization, and Confidence Scoring

**Files:**
- Create: `api/app/pipeline/normalize.py`
- Test: `api/tests/test_normalize.py`

**Interfaces:**
- Consumes: `LabObservationRaw` (Task 2), `ocr_lines: list[dict]` (JSONB from `Document.ocr_lines`), `lab_dictionary: dict` (loaded from `api/data/lab_dictionary.json`)
- Produces:
  ```python
  @dataclass
  class ScoredObservation:
      obs: LabObservationRaw
      canonical_test_id: str | None
      normalized_unit: str | None
      normalized_ref_low: float | None
      normalized_ref_high: float | None
      grounding_passed: bool
      confidence: float          # 0.0–1.0; drives review highlighting only

  def score_observations(
      raw_obs: list[LabObservationRaw],
      ocr_lines: list[dict],
      lab_dictionary: dict,
  ) -> list[ScoredObservation]
  ```

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_normalize.py
from app.pipeline.normalize import score_observations, ScoredObservation
from app.pipeline.extract import LabObservationRaw

OCR_LINES = [
    {"id": 1, "page": 1, "text": "Hemoglobin", "bbox": [0,0,100,20], "conf": 0.96, "row_id": 1},
    {"id": 2, "page": 1, "text": "13.2",       "bbox": [110,0,160,20], "conf": 0.93, "row_id": 1},
]
LAB_DICT = {
    "hemoglobin": {"canonical_id": "HGB", "standard_unit": "g/dL", "ref_low": 12.0, "ref_high": 16.0, "aliases": ["hgb", "hb"]}
}

def _obs(**kw) -> LabObservationRaw:
    defaults = dict(test_name="Hemoglobin", value=13.2, value_text=None,
                    unit="g/dL", ref_low=12.0, ref_high=16.0, flag="normal", line_ids=[1,2])
    return LabObservationRaw(**(defaults | kw))

def test_grounding_passes_when_value_in_lines():
    results = score_observations([_obs()], OCR_LINES, LAB_DICT)
    assert results[0].grounding_passed is True

def test_grounding_fails_when_value_not_in_lines():
    results = score_observations([_obs(value=99.9, line_ids=[1,2])], OCR_LINES, LAB_DICT)
    assert results[0].grounding_passed is False
    assert results[0].confidence < 0.5

def test_dictionary_match_sets_canonical_id():
    results = score_observations([_obs()], OCR_LINES, LAB_DICT)
    assert results[0].canonical_test_id == "HGB"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.pipeline.normalize'`

- [ ] **Step 3: Implement `score_observations` in `api/app/pipeline/normalize.py`**

Grounding check logic:
- Collect the `text` of all `ocr_lines` whose `id` is in `obs.line_ids`.
- The check passes if the numeric string of `obs.value` (e.g., `"13.2"`) appears in any of those texts, **or** if `obs.value` is `None` (text-only observation).

Confidence formula (all components 0–1, equal weight):
1. `ocr_conf`: mean `conf` of referenced OCR lines (default 0.5 if line_ids empty).
2. `grounding`: 1.0 if passed, 0.0 if failed.
3. `dict_match`: 1.0 if `canonical_test_id` found, 0.7 if not.
4. `unit_valid`: 1.0 if `normalized_unit` matches dict standard, 0.7 if absent, 0.4 if mismatch.
5. `range_plausible`: 1.0 if value within `[ref_low - 20%, ref_high + 20%]`, 0.6 if outside, 1.0 if value is None.

`confidence = mean([ocr_conf, grounding, dict_match, unit_valid, range_plausible])`

Dictionary lookup: lowercase `obs.test_name`, check exact key then aliases.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_normalize.py -v`
Expected: PASS with 3 passed

- [ ] **Step 5: Commit**

```bash
git add api/app/pipeline/normalize.py api/tests/test_normalize.py
git commit -m "feat(pipeline): add grounding check, dictionary normalization, and confidence scoring"
```

---

## Task 4: Pipeline Integration — Extraction Stage + Rate-Limit Handling

**Files:**
- Modify: `api/app/services/documents.py` (extend `process_document_background`)
- Test: `api/tests/test_extraction_pipeline.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`redact_text`, `extract_page`, `score_observations`), `OpenAICompatClient`, `Extraction` + `Observation` models.
- Produces: pipeline transitions `ocr → extracting → needs_review | rate_limited | failed`; `Extraction` row written; pending `Observation` rows written.

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_extraction_pipeline.py
import json
from unittest.mock import patch, MagicMock
from app.llm.client import LlmResponse

MOCK_LLM_RESPONSE = json.dumps({
    "lab_name": "Test Lab", "report_date": "2026-10-01",
    "observations": [{
        "test_name": "Hemoglobin", "value": 13.2, "value_text": None,
        "unit": "g/dL", "ref_low": 12.0, "ref_high": 16.0,
        "flag": "normal", "line_ids": [1],
    }]
})

def test_pipeline_creates_pending_observations(db_session, sample_document_with_ocr):
    """After extraction stage, document has status=needs_review and pending observations."""
    doc_id = sample_document_with_ocr.id

    with patch("app.services.documents.OpenAICompatClient") as MockClient:
        instance = MockClient.return_value
        instance.chat.return_value = LlmResponse(
            content=MOCK_LLM_RESPONSE, prompt_tokens=50, completion_tokens=30,
            latency_ms=100, model_used="mock-model", key_label="k1",
        )
        from app.services.documents import _run_extraction_stage
        _run_extraction_stage(doc_id, db_session)

    from app.models import Document, Observation
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc.status == "needs_review"
    obs = db_session.query(Observation).filter(Observation.document_id == doc_id).all()
    assert len(obs) >= 1
    assert obs[0].status == "pending"

def test_pipeline_sets_rate_limited_on_exhausted_keys(db_session, sample_document_with_ocr):
    doc_id = sample_document_with_ocr.id
    with patch("app.services.documents.OpenAICompatClient") as MockClient:
        MockClient.return_value.chat.side_effect = RuntimeError(
            "All configured API keys are currently exhausted"
        )
        from app.services.documents import _run_extraction_stage
        _run_extraction_stage(doc_id, db_session)

    from app.models import Document
    doc = db_session.query(Document).filter(Document.id == doc_id).first()
    assert doc.status == "rate_limited"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_extraction_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: Add `_run_extraction_stage` to `api/app/services/documents.py`**

Extract the new extraction stage as a standalone helper `_run_extraction_stage(doc_id: int, db: Session) -> None` so it can be called from `process_document_background` and independently by the retry endpoint (Task 5).

Sequence inside `_run_extraction_stage`:
1. Set `doc.status = "extracting"`, commit.
2. Load `lab_dictionary.json` once (cache module-level after first load).
3. For each page (sequential), call `redact_text(page_ocr_text, patient_name)`.
4. Compute `input_hash = sha256(redacted_text + prompt_version + model)`.
5. Check `db.query(Extraction).filter_by(document_id=doc_id, input_hash=input_hash).first()` — skip page if cached.
6. Call `extract_page(redacted_text, line_ids, client)`.
7. On `RuntimeError` (all keys exhausted): set `doc.status = "rate_limited"`, commit, return.
8. On `ExtractionFailed`: set `doc.status = "failed"`, commit, return.
9. Write `Extraction` row with `raw_json`, `field_confidence`, `input_hash`, `model`, `prompt_version`.
10. Call `score_observations(raw_obs, ocr_lines, lab_dictionary)`.
11. Write pending `Observation` rows (delete previous pending ones for this doc first).
12. After all pages: set `doc.status = "needs_review"`, commit.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_extraction_pipeline.py -v`
Expected: PASS with 2 passed

- [ ] **Step 5: Wire into `process_document_background`**

After the existing OCR block, call `_run_extraction_stage(doc.id, db)` instead of setting `needs_review` directly.

- [ ] **Step 6: Commit**

```bash
git add api/app/services/documents.py api/tests/test_extraction_pipeline.py
git commit -m "feat(pipeline): integrate extraction stage with rate-limit handling into background worker"
```

---

## Task 5: Extraction and Observation REST Endpoints

**Files:**
- Modify: `api/app/routers/documents.py` (add extraction + confirm + retry endpoints)
- Create: `api/app/routers/observations.py`
- Modify: `api/app/main.py` (register observations router)
- Modify: `api/app/schemas.py` (add `ObservationRead`, `ObservationPatch`, `ExtractionRead`)
- Test: `api/tests/test_review_endpoints.py`

**Interfaces:**
- Produces:
  - `GET /api/v1/documents/{id}/extraction` → `ExtractionRead` (observations + OCR lines + confidence per observation)
  - `PATCH /api/v1/observations/{id}` → `ObservationRead`
  - `POST /api/v1/documents/{id}/confirm` → `{"confirmed": N}` count
  - `POST /api/v1/documents/{id}/retry` → `{"status": "queued"}` (re-queues `rate_limited` docs)

- [ ] **Step 1: Write the failing test**

```python
# api/tests/test_review_endpoints.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "change-me"}

def test_extraction_endpoint_404_on_missing():
    r = client.get("/api/v1/documents/9999/extraction", headers=HEADERS)
    assert r.status_code == 404

def test_patch_observation_updates_value(db_with_pending_obs):
    obs_id = db_with_pending_obs
    r = client.patch(f"/api/v1/observations/{obs_id}", headers=HEADERS,
                     json={"value_num": 14.5, "unit": "g/dL"})
    assert r.status_code == 200
    assert r.json()["value_num"] == 14.5

def test_patch_observation_blocked_after_confirm(db_with_confirmed_obs):
    obs_id = db_with_confirmed_obs
    r = client.patch(f"/api/v1/observations/{obs_id}", headers=HEADERS,
                     json={"value_num": 99.0})
    assert r.status_code == 409

def test_confirm_sets_observations_confirmed(db_with_pending_obs_doc):
    doc_id, obs_id = db_with_pending_obs_doc
    r = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["confirmed"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_review_endpoints.py -v`
Expected: FAIL with 404s / missing routes

- [ ] **Step 3: Add schemas to `api/app/schemas.py`**

```python
class ObservationRead(BaseModel):
    id: int
    test_name: str
    value_num: float | None
    value_text: str | None
    unit: str | None
    ref_low: float | None
    ref_high: float | None
    flag: str | None
    collected_at: date | None
    page_no: int
    source_line_ids: list[int] | None
    status: str
    confidence: float | None   # from Extraction.field_confidence[str(id)]
    model_config = ConfigDict(from_attributes=True)

class ObservationPatch(BaseModel):
    test_name: str | None = None
    value_num: float | None = None
    value_text: str | None = None
    unit: str | None = None
    ref_low: float | None = None
    ref_high: float | None = None
    flag: str | None = None
    collected_at: date | None = None

class ExtractionRead(BaseModel):
    document_id: int
    status: str
    observations: list[ObservationRead]
    ocr_lines: list[dict]
```

- [ ] **Step 4: Implement endpoints**

In `api/app/routers/documents.py`:
- `GET /{document_id}/extraction`: query `Observation` where `document_id=id`, attach `confidence` from latest `Extraction.field_confidence` keyed by `str(obs.id)`, return `ExtractionRead`.
- `POST /{document_id}/confirm`: set all `pending` observations to `confirmed`, set `doc.status = "confirmed"`, commit, return `{"confirmed": N}`.
- `POST /{document_id}/retry`: if `doc.status == "rate_limited"`, re-enqueue `_run_extraction_stage` as background task; else 409.

Create `api/app/routers/observations.py`:
- `PATCH /observations/{id}`: if observation's document status is `confirmed`, return 409. Otherwise apply non-None fields from `ObservationPatch`, commit.

Register in `api/app/main.py`:
```python
from app.routers import observations
app.include_router(observations.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_review_endpoints.py -v`
Expected: PASS with 4 passed

- [ ] **Step 6: Run full backend test suite**

Run: `docker compose exec -T api pytest -v`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add api/app/routers/documents.py api/app/routers/observations.py \
        api/app/main.py api/app/schemas.py api/tests/test_review_endpoints.py
git commit -m "feat(api): add extraction, observation edit, confirm, and retry endpoints"
```

---

## Task 6: Flutter Review Screen

**Files:**
- Create: `app/lib/features/review/observation_model.dart`
- Create: `app/lib/features/review/review_controller.dart`
- Create: `app/lib/features/review/review_screen.dart`
- Modify: `app/lib/features/navigation/app_router.dart` (add `/documents/:id/review` route)
- Modify: `app/lib/features/documents/documents_screen.dart` (tap chip navigates to review when `needs_review`)
- Test: `app/test/review_screen_test.dart`

**Interfaces:**
- Consumes: `GET /api/v1/documents/{id}/extraction`, `GET /api/v1/documents/{id}/pages/{n}.png`, `PATCH /api/v1/observations/{id}`, `POST /api/v1/documents/{id}/confirm`
- Produces:
  ```dart
  // observation_model.dart
  class ObservationModel {
    final int id;
    final String testName;
    final double? valueNum;
    final String? valueText;
    final String? unit;
    final double? refLow;
    final double? refHigh;
    final String? flag;
    final String? collectedAt;
    final int pageNo;
    final List<int> sourceLineIds;
    final String status;
    final double? confidence;
  }
  ```

- [ ] **Step 1: Write the failing widget test**

```dart
// app/test/review_screen_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:swasthyastats/features/review/review_screen.dart';

void main() {
  testWidgets('ReviewScreen compiles and renders placeholder/skeleton', (tester) async {
    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: ReviewScreen(documentId: 1)),
      ),
    );
    expect(find.byType(ReviewScreen), findsOneWidget);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/review_screen_test.dart`
Expected: FAIL with `Target file not found`

- [ ] **Step 3: Implement `observation_model.dart`**

Plain Dart class with `fromJson(Map<String, dynamic>)` factory.

- [ ] **Step 4: Implement `review_controller.dart`**

`ReviewNotifier` loads `GET /extraction`, sorts observations by `confidence` ascending (nulls last), exposes `patchObservation(int id, Map<String, dynamic> patch)`, and `confirmAll()`.

- [ ] **Step 5: Implement `review_screen.dart`**

Layout (responsive, matches spec §12):
- Mobile (< 600 px wide): page image at top (constrained to 40 % of screen height, pinch-zoom via `InteractiveViewer`), scrollable observation rows below.
- Wide (≥ 600 px): left pane = page image, right pane = observation rows list.
- Each row: test name, editable value field, unit, reference range, flag chip, confidence dot (red < 0.6, amber 0.6–0.8, green > 0.8).
- Tapping a row highlights the corresponding page (set selected `pageNo`; image pane re-fetches that page).
- "Confirm all" button at bottom: calls `confirmAll()`, shows loading, pops on success.
- Page image fetched via `ApiClient.get("/documents/$docId/pages/$pageNo.png")` returning bytes → `Image.memory`.

- [ ] **Step 6: Wire route and navigation**

In `app_router.dart`, add `GoRoute(path: '/documents/:id/review', builder: (_, state) => ReviewScreen(documentId: int.parse(state.pathParameters['id']!)))`.
In `documents_screen.dart`, change the status chip tap for `needs_review` to `context.go('/documents/$id/review')`.

- [ ] **Step 7: Run test to verify it passes**

Run: `cd app && flutter test test/review_screen_test.dart`
Expected: PASS

- [ ] **Step 8: Build web release**

Run: `cd app && flutter build web --wasm --release`
Expected: build succeeds

- [ ] **Step 9: Commit**

```bash
git add app/lib/features/review/ app/lib/features/navigation/app_router.dart \
        app/lib/features/documents/documents_screen.dart app/test/review_screen_test.dart
git commit -m "feat(flutter): add review screen with observation editing and confirm flow"
```

---

## Task 7: Usage Panel + Rate-Limited Status in Flutter

**Files:**
- Modify: `app/lib/features/settings/settings_screen.dart` (wire Usage panel to `GET /usage`)
- Modify: `app/lib/features/documents/documents_screen.dart` (show "Rate limited — tap to retry" chip)
- Test: `app/test/documents_screen_test.dart`

**Interfaces:**
- Consumes: existing `GET /api/v1/usage` endpoint, `POST /api/v1/documents/{id}/retry`

- [ ] **Step 1: Write the failing test extension**

Add rate-limited status chip test case to `app/test/documents_screen_test.dart`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/documents_screen_test.dart`
Expected: FAIL

- [ ] **Step 3: Extend `documents_screen.dart`**

Add `rate_limited` as a named status chip (amber color, label "Rate limited", tap calls `POST /documents/$id/retry` then refreshes list).

- [ ] **Step 4: Wire Usage panel in `settings_screen.dart`**

`GET /usage` already returns `{tokens_today, calls_today, last_error, rate_limit_status}`. Render as a card at the bottom of the settings screen.

- [ ] **Step 5: Run tests to verify passing**

Run: `cd app && flutter test`
Expected: all Flutter tests pass

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/documents/documents_screen.dart \
        app/lib/features/settings/settings_screen.dart \
        app/test/documents_screen_test.dart
git commit -m "feat(flutter): show rate_limited chip with retry, wire usage panel in settings"
```

---

## Task 8: Bake-offs and Eval Update

**Files:**
- Modify: `eval/RESULTS.md`
- Modify: `eval/run_eval.py` (add extraction F1 scoring)

**Interfaces:**
- Consumes: `eval/samples/`, `eval/ground_truth/`
- Produces: F1 score, token cost per document, rate-limit test results logged to `eval/RESULTS.md`

- [ ] **Step 1: Add extraction F1 scoring to `eval/run_eval.py`**

Add `score_extraction(predicted: list[dict], ground_truth: list[dict]) -> float` that matches on `test_name` (case-insensitive) and checks `value_num` within ± 0.05 tolerance. Print field F1 at the end of the eval run.

- [ ] **Step 2: Run extraction eval**

```bash
docker compose exec -T api python eval/run_eval.py
```
Record output in `eval/RESULTS.md`.

- [ ] **Step 3: Bake-off — Groq model**

Test 2–3 available models via Settings. Record field F1, valid-JSON rate, tokens/doc, latency in `eval/RESULTS.md`.

- [ ] **Step 4: Bake-off — key pool behavior**

Force one key to 429. Confirm failover and recovery. Log in `eval/RESULTS.md`.

- [ ] **Step 5: Bake-off — provider portability**

Change `base_url` to a secondary provider (e.g. OpenRouter). Verify extraction works with zero code changes.

- [ ] **Step 6: Commit**

```bash
git add eval/run_eval.py eval/RESULTS.md
git commit -m "eval: add extraction F1 scoring and log Week 3 bake-off results"
```

---

## Verification Plan

### Automated Tests

```bash
# Backend — all tests
docker compose exec -T api pytest -v

# Flutter — all widget tests
cd app && flutter test
```

### Manual Verification (exit criteria)

| Check | Expected |
|-------|----------|
| Upload a lab report photo → wait → refresh | Status transitions `queued → normalizing → ocr → extracting → needs_review` |
| Open review screen on phone | Page image renders; observations appear sorted low-confidence first |
| Edit one observation value | `PATCH` succeeds; value updates in UI |
| Tap "Confirm all" | Status changes to `confirmed`; observations locked |
| Force rate limit (bad key) | Document shows "Rate limited" chip; retry re-queues |
| Extraction F1 on eval set | ≥ 85 % on clean synthetic documents (target per spec §16) |
| Latency per page | ≤ 90 s (OCR + LLM on CPU + Groq) — record actual |
| `POST /confirm` then `PATCH /observation` | Returns 409 Conflict |
| Week 3 exit condition | Scan → confirmed observations end-to-end on a phone ✅ |
