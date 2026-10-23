# PWA Enhancements: Offline Caching, Doctor Extraction & Sorting, Review Quick-Add, and RAG UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the prototype PWA with offline caching for results, auto-refreshing documents, doctor name extraction and sorting, interactive citation bottom sheets, chat history reset with starter chips, abnormal-only quick filters, trend delta indicators, and a comprehensive inline dialog to manually add missed tests during document review.

**Architecture:** 
1. **Backend**: Extend database schema with `doctor_name` on `Document`, update extraction prompt and Pydantic schemas, add `POST /api/v1/documents/{id}/observations` for manual observation addition, and calculate delta values (`delta_value`, `delta_percent`) in `GET /api/v1/tests`.
2. **Offline & Storage**: Implement `LocalCacheService` using `SharedPreferences` to cache documents and lab summaries so they render gracefully when offline.
3. **Frontend UI**: Upgrade `DocumentsScreen` (auto-refresh, doctor sorting, offline view), `ReviewScreen` (abnormal-only filter, inline quick-add dialog), `LabsScreen` (abnormal filter, summary delta chips), and `AskScreen` (suggested starter chips, interactive citation bottom sheets, reset chat).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, PostgreSQL + pgvector, Flutter Web (Wasm), Riverpod, Dio, `shared_preferences`, `flutter_markdown_plus`.

**Spec:** Current prototype design in `prototype-architecture.md` and user-specified feature requirements.

## Global Constraints

- Backend must maintain 100% test compatibility: all existing 58 backend tests must remain green.
- Flutter analyzer must report 0 issues (`flutter analyze`).
- No external network dependencies introduced beyond existing open-source packages.
- All code changes strictly bounded to target feature areas.

## Review Focus

1. **Offline cache resilience**: When network is disconnected, `DocumentsScreen` and `LabsScreen` must render cached data without throwing unhandled exceptions or blank screens.
2. **Missing test addition validation**: The manual add test dialog in `ReviewScreen` must validate that `test_name` is non-empty and numerical fields (`value_num`, `ref_low`, `ref_high`) parse properly or fall back to `value_text`.
3. **Citation sheet crash safety**: If a cited observation ID or document ID has been deleted or cannot be resolved, the bottom sheet must display a graceful fallback message instead of throwing an unhandled route error.
4. **Auto-refresh timer cleanup**: The polling timers in `DocumentsController` must cancel on disposal to prevent memory leaks and duplicate background calls.
5. **Doctor name sorting**: Sorting documents by doctor name must handle documents where `doctor_name` is null or empty, ordering them last in ascending sort.

---

### Task 1: Backend Doctor Name Extraction, Storage & Document Sorting

**Files:**
- Create: `api/alembic/versions/002_add_doctor_name.py`
- Modify: `api/app/models.py:41-67`
- Modify: `api/app/schemas.py:99-135`
- Modify: `api/app/pipeline/extract.py:28-45`
- Modify: `api/app/routers/documents.py:32-41`
- Test: `api/tests/test_extract.py`
- Test: `api/tests/test_documents_api.py`

**Interfaces:**
- Consumes: `LabReportRaw` in `api/app/pipeline/extract.py`
- Produces: `doctor_name: Optional[str]` on `Document`, `LabReportRaw`, and `DocumentRead`. `GET /api/v1/documents?sort_by=...` query parameter supporting `date_desc`, `date_asc`, `doctor_asc`, `doctor_desc`, `filename`.

- [ ] **Step 1: Write failing tests for doctor name extraction and document sorting**

```python
# In api/tests/test_extract.py:
def test_extract_lab_report_with_doctor_name():
    from app.pipeline.extract import LabReportRaw, EXTRACTION_SYSTEM_PROMPT
    assert "doctor" in EXTRACTION_SYSTEM_PROMPT.lower()
    raw = LabReportRaw(lab_name="Central Lab", doctor_name="Dr. Jane Doe")
    assert raw.doctor_name == "Dr. Jane Doe"

# In api/tests/test_documents_api.py:
def test_list_documents_sort_by_doctor(client, auth_headers):
    resp = client.get("/api/v1/documents?sort_by=doctor_asc", headers=auth_headers)
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api pytest api/tests/test_extract.py -k test_extract_lab_report_with_doctor_name`
Expected: FAIL

- [ ] **Step 3: Implement doctor_name in database model, migration, schema, extraction prompt, and sorting query**

1. In `api/app/models.py`: Add `doctor_name = Column(String(255), nullable=True)` to `Document`.
2. In `api/alembic/versions/002_add_doctor_name.py`: Create migration adding `doctor_name` column to `documents`.
3. In `api/app/schemas.py`: Add `doctor_name: Optional[str] = None` to `LabReportSchema` and `DocumentRead`.
4. In `api/app/pipeline/extract.py`: Add `doctor_name: Optional[str] = None` to `LabReportRaw`, and instruct `EXTRACTION_SYSTEM_PROMPT` to extract referring doctor or physician name into `doctor_name` if present.
5. In `api/app/services/documents.py`: In `_run_extraction_stage`, assign `doc.doctor_name = report.doctor_name` when `report.doctor_name` is present.
6. In `api/app/routers/documents.py`: Add `sort_by: Optional[str] = Query("date_desc")` to `list_documents`, handling `doctor_asc`, `doctor_desc`, `date_asc`, `date_desc`, and `filename`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api pytest api/tests/test_extract.py api/tests/test_documents_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/
git commit -m "feat(api): extract doctor name and support document sorting by doctor"
```

---

### Task 2: Backend Manual Observation Addition & Summary Delta Indicators

**Files:**
- Modify: `api/app/schemas.py:136-180`
- Modify: `api/app/routers/documents.py:126-160`
- Modify: `api/app/routers/charts.py:17-65`
- Test: `api/tests/test_review_endpoints.py`
- Test: `api/tests/test_charts_api.py`

**Interfaces:**
- Consumes: `Observation` in `api/app/models.py`
- Produces:
  - `POST /api/v1/documents/{document_id}/observations` returning created `ObservationRead`.
  - `LabTestSummary` fields: `previous_value: Optional[float]`, `delta_value: Optional[float]`, `delta_percent: Optional[float]`, `is_abnormal: bool`.

- [ ] **Step 1: Write failing tests for manual observation addition and delta indicators**

```python
# In api/tests/test_review_endpoints.py:
def test_manual_add_observation_to_document(client, auth_headers):
    # Upload test doc, then POST /api/v1/documents/{id}/observations
    payload = {
        "test_name": "Serum Ferritin",
        "value_num": 150.0,
        "unit": "ng/mL",
        "ref_low": 30.0,
        "ref_high": 400.0,
        "flag": "normal",
        "page_no": 1
    }
    resp = client.post(f"/api/v1/documents/{doc_id}/observations", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    assert resp.json()["test_name"] == "Serum Ferritin"

# In api/tests/test_charts_api.py:
def test_lab_test_summary_includes_deltas(client, auth_headers):
    resp = client.get("/api/v1/tests", headers=auth_headers)
    assert resp.status_code == 200
    item = resp.json()[0]
    assert "previous_value" in item
    assert "delta_value" in item
    assert "is_abnormal" in item
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api pytest api/tests/test_review_endpoints.py -k test_manual_add_observation_to_document`
Expected: FAIL (404 or 405 endpoint missing)

- [ ] **Step 3: Implement ObservationCreate schema, add observation endpoint, and delta calculations**

1. In `api/app/schemas.py`: Define `ObservationCreate(BaseModel)` with `test_name`, `value_num`, `value_text`, `unit`, `ref_low`, `ref_high`, `flag`, `page_no: int = 1`, `collected_at: Optional[date] = None`.
2. In `api/app/schemas.py`: Add `previous_value: Optional[float] = None`, `delta_value: Optional[float] = None`, `delta_percent: Optional[float] = None`, `is_abnormal: bool = False` to `LabTestSummary`.
3. In `api/app/routers/documents.py`: Add `POST /{document_id}/observations`:
   - Checks document exists and is not confirmed (409 Conflict if confirmed).
   - Resolves canonical test ID using `_find_canonical_test_id`.
   - Creates new `Observation` with `status="pending"`, `confidence=1.0`.
   - Returns 201 Created with `ObservationRead`.
4. In `api/app/routers/charts.py`: In `list_available_tests`, track first observation as `latest_value` and second observation as `previous_value`. Compute `delta_value = latest_value - previous_value`, `delta_percent = ((latest_value - previous_value) / previous_value) * 100`, and `is_abnormal = latest_flag in ["high", "low", "critical"] or (ref_low is not None and latest_value < ref_low) or (ref_high is not None and latest_value > ref_high)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api pytest api/tests/test_review_endpoints.py api/tests/test_charts_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/
git commit -m "feat(api): add manual observation endpoint and compute summary deltas"
```

---

### Task 3: Flutter Local Cache & Offline Results Support

**Files:**
- Create: `app/lib/core/local_cache.dart`
- Modify: `app/lib/features/documents/documents_controller.dart:10-60`
- Modify: `app/lib/features/labs/labs_controller.dart:10-50`
- Modify: `app/lib/features/documents/documents_screen.dart:240-275`
- Modify: `app/lib/features/labs/labs_screen.dart:54-95`
- Test: `app/test/offline_cache_test.dart`

**Interfaces:**
- Consumes: `shared_preferences`
- Produces: `localCacheServiceProvider`, providing `Future<void> cacheDocuments(List<Map<String, dynamic>>) json`, `Future<List<Map<String, dynamic>>> getCachedDocuments()`, `Future<void> cacheLabs(List<Map<String, dynamic>>) json`, `Future<List<Map<String, dynamic>>> getCachedLabs()`.

- [ ] **Step 1: Write test for LocalCacheService and offline graceful degradation**

```dart
// In app/test/offline_cache_test.dart
void main() {
  test('LocalCacheService saves and retrieves documents and labs', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final cache = LocalCacheService(prefs);
    await cache.cacheDocuments([{'id': 1, 'filename': 'test.pdf', 'status': 'confirmed'}]);
    final docs = await cache.getCachedDocuments();
    expect(docs.length, 1);
    expect(docs.first['filename'], 'test.pdf');
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/offline_cache_test.dart`
Expected: FAIL (LocalCacheService not defined)

- [ ] **Step 3: Implement LocalCacheService and integrate into Documents & Labs controllers**

1. Create `app/lib/core/local_cache.dart` with JSON serialization to `SharedPreferences` keys `cache_documents` and `cache_labs`.
2. In `documents_controller.dart`: In `_fetchDocuments()`, on success write to cache. On `DioException` or network failure, if cache has documents, return cached list.
3. In `labs_controller.dart`: In `_fetchTests()`, on success write to cache; on failure, load cached lab tests.
4. In `documents_screen.dart` and `labs_screen.dart`: Remove the blocking full-screen offline blocker. Instead, display an amber `Container` banner at the top of the body: `Row(children: [Icon(Icons.cloud_off), Text("Offline mode — showing cached results")])` when `isOffline` is true, while rendering the document/lab list underneath.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && flutter test test/offline_cache_test.dart`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/
git commit -m "feat(app): add local cache service and offline results display"
```

---

### Task 4: Flutter Documents Page Auto-Refresh & Doctor Sorting

**Files:**
- Modify: `app/lib/features/documents/document_model.dart:1-35`
- Modify: `app/lib/features/documents/documents_controller.dart:7-50`
- Modify: `app/lib/features/documents/documents_screen.dart:18-80, 280-350`
- Test: `app/test/documents_screen_test.dart`

**Interfaces:**
- Consumes: `DocumentItem` with `doctorName: String?`
- Produces: Sort options dropdown/menu in `DocumentsScreen` (Date Newest/Oldest, Doctor Name A-Z/Z-A, Filename) and periodic auto-refresh polling while documents are in progress.

- [ ] **Step 1: Write test for Doctor Name parsing and sorting options**

```dart
// In app/test/documents_screen_test.dart:
test('DocumentItem parses doctorName from JSON', () {
  final doc = DocumentItem.fromJson({
    'id': 1,
    'filename': 'report.pdf',
    'status': 'confirmed',
    'doctor_name': 'Dr. Sharma',
    'created_at': '2026-10-23T00:00:00Z',
    'page_count': 1,
    'patient_id': 1,
  });
  expect(doc.doctorName, 'Dr. Sharma');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/documents_screen_test.dart`
Expected: FAIL (`doctorName` getter not found)

- [ ] **Step 3: Update DocumentItem, polling in DocumentsController, and DocumentsScreen UI**

1. In `document_model.dart`: Add `final String? doctorName;` to `DocumentItem`, populate from `json['doctor_name']`.
2. In `documents_controller.dart`: Ensure polling timer runs every 3 seconds when any document has status `queued`, `normalizing`, `ocr`, or `extracting`. Also provide a periodic light check every 15 seconds when on screen.
3. In `documents_screen.dart`:
   - Add a `PopupMenuButton<String>` or sorting dropdown in `AppBar` actions with choices: `Date (Newest)`, `Date (Oldest)`, `Doctor (A-Z)`, `Doctor (Z-A)`.
   - Apply client-side sorting to the document list based on selection.
   - In each document card (`_buildDocumentCard`), if `doc.doctorName != null`, display a doctor chip/row: `Icon(Icons.person_outline, size: 14), Text(doc.doctorName!)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && flutter test test/documents_screen_test.dart`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/
git commit -m "feat(app): add document auto-refresh, doctor name extraction display and sorting"
```

---

### Task 5: Flutter Review Screen: Abnormal Filter & Inline Quick Add Dialog

**Files:**
- Modify: `app/lib/features/review/observation_model.dart:1-40`
- Modify: `app/lib/features/review/review_controller.dart:20-80`
- Modify: `app/lib/features/review/review_screen.dart:60-150, 250-320`
- Test: `app/test/review_screen_test.dart`

**Interfaces:**
- Consumes: `POST /api/v1/documents/{documentId}/observations`
- Produces:
  - `addObservation({...})` on `ReviewController`.
  - Filter chip "Abnormal only" in `ReviewScreen`.
  - Comprehensive "Add missed test" modal dialog in `ReviewScreen`.

- [ ] **Step 1: Write test for ReviewScreen quick-add and abnormal filtering**

```dart
// In app/test/review_screen_test.dart:
test('ObservationModel calculates isAbnormal correctly', () {
  final highObs = ObservationModel(
    id: 1,
    testName: 'Glucose',
    valueNum: 160.0,
    refLow: 70.0,
    refHigh: 99.0,
    flag: 'high',
    pageNo: 1,
    status: 'pending',
  );
  expect(highObs.isAbnormal, true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/review_screen_test.dart`
Expected: FAIL (`isAbnormal` getter not found)

- [ ] **Step 3: Implement isAbnormal, addObservation in controller, and ReviewScreen dialog**

1. In `observation_model.dart`: Add getter `bool get isAbnormal => flag == 'high' || flag == 'low' || flag == 'critical' || (refLow != null && valueNum != null && valueNum! < refLow!) || (refHigh != null && valueNum != null && valueNum! > refHigh!);`.
2. In `review_controller.dart`: Add `Future<bool> addObservation(Map<String, dynamic> data) async`:
   - Sends `POST /documents/$documentId/observations` via API client.
   - On response, appends created `ObservationModel` to `state.observations` and updates state.
3. In `review_screen.dart`:
   - In filter bar (where page chips live), add a `FilterChip(label: Text('Abnormal only ($abnormalCount)'), selected: _filterAbnormalOnly, onSelected: (val) => setState(() => _filterAbnormalOnly = val))` with an alert icon.
   - When active, `filteredObs` filters by `obs.isAbnormal`.
   - Add an "Add test" action button in `review_screen.dart` header/toolbar.
   - Implement `_showAddTestDialog`:
     - Input fields: Test Name (required), Value (with number or text option), Unit, Ref Low (number), Ref High (number), Flag (dropdown: none, normal, high, low, critical), Page Number (dropdown 1..pageCount, defaulted to current page).
     - Validates input and calls `reviewController.addObservation(...)`.
     - Displays snackbar on success.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && flutter test test/review_screen_test.dart`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/
git commit -m "feat(app): add abnormal filter and inline quick-add test dialog in review screen"
```

---

### Task 6: Flutter Labs Screen: Abnormal Quick Filter & Summary Delta Indicators

**Files:**
- Modify: `app/lib/features/labs/lab_model.dart:1-37`
- Modify: `app/lib/features/labs/labs_screen.dart:40-260`
- Test: `app/test/labs_screen_test.dart`

**Interfaces:**
- Consumes: `previous_value`, `delta_value`, `delta_percent`, `is_abnormal` from `GET /api/v1/tests`.
- Produces: Abnormal-only quick filter chip and delta trend badges (`↑ +X.X`, `↓ -X.X`) on lab cards and favorites.

- [ ] **Step 1: Write test for LabTestSummary deltas and abnormal flag**

```dart
// In app/test/labs_screen_test.dart:
test('LabTestSummary parses delta fields and isAbnormal', () {
  final summary = LabTestSummary.fromJson({
    'test_name': 'Hemoglobin',
    'count': 3,
    'latest_value': 14.5,
    'previous_value': 13.5,
    'delta_value': 1.0,
    'delta_percent': 7.4,
    'is_abnormal': false,
  });
  expect(summary.deltaValue, 1.0);
  expect(summary.isAbnormal, false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/labs_screen_test.dart`
Expected: FAIL (`deltaValue` not defined on `LabTestSummary`)

- [ ] **Step 3: Update LabTestSummary model and render deltas and filter in LabsScreen**

1. In `lab_model.dart`: Add `previousValue: double?`, `deltaValue: double?`, `deltaPercent: double?`, `isAbnormal: bool` to `LabTestSummary`.
2. In `labs_screen.dart`:
   - Below search bar, add a row of filter chips: "All Tests" and "Abnormal Only" (with count badge).
   - In test list item (`ListTile`) and in favorite cards (`_buildFavouriteCard`):
     - When `test.deltaValue != null`: render a compact trend indicator next to the latest value:
       - If `deltaValue > 0`: `Row(children: [Icon(Icons.arrow_upward, size: 12, color: Colors.blue), Text('+${deltaValue.toStringAsFixed(1)}')])`
       - If `deltaValue < 0`: `Row(children: [Icon(Icons.arrow_downward, size: 12, color: Colors.deepOrange), Text('${deltaValue.toStringAsFixed(1)}')])`
       - If `deltaValue == 0`: `Text('±0.0', style: TextStyle(color: Colors.grey))`
     - Display previous value subtitle (e.g. `prev: 13.5`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && flutter test test/labs_screen_test.dart`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/
git commit -m "feat(app): add abnormal quick filter and summary delta indicators in labs"
```

---

### Task 7: Flutter Ask Screen: Suggested Starter Chips, Interactive Citation Bottom Sheets & Reset History

**Files:**
- Modify: `app/lib/features/ask/ask_controller.dart:1-60`
- Modify: `app/lib/features/ask/ask_screen.dart:95-313`
- Test: `app/test/ask_screen_test.dart`

**Interfaces:**
- Consumes: `CitationRef` and chat message state.
- Produces:
  - Starter suggestion chips when chat is empty.
  - Modal bottom sheet displaying detailed citation card with direct action button.
  - Clear/reset conversation history button with confirmation dialog.

- [ ] **Step 1: Write test for AskScreen starter chips and clear history**

```dart
// In app/test/ask_screen_test.dart:
testWidgets('AskScreen displays starter chips when empty', (tester) async {
  // Mount AskScreen with empty message list
  // Expect to find starter chip texts like 'What was my last HbA1c?'
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/ask_screen_test.dart`
Expected: FAIL (Starter chips not present)

- [ ] **Step 3: Implement starter chips, citation bottom sheet, and clear history**

1. In `ask_screen.dart`:
   - In the empty state view: Add a wrap of suggested starter chips:
     - "What was my last HbA1c?"
     - "Are any of my test results abnormal?"
     - "What are my cholesterol levels?"
     - "List all my recorded blood tests"
     - Tapping a chip populates `_textController.text = chipText` and immediately calls `_handleSend()`.
2. In `ask_screen.dart`: Replace the `onPressed` handler in `_CitationChip`:
   - Instead of immediately navigating away, open `showModalBottomSheet(context: context, builder: (ctx) => _CitationBottomSheet(citation: citation))`.
   - Bottom sheet fetches or displays observation/document details:
     - For `obs:ID`: Displays test name, numeric value/text, unit, reference range, status badge, date, and a "View Trend in Labs" button.
     - For `doc:ID`: Displays document title, date, page number, and an "Open Document" button.
3. In `ask_screen.dart` and `ask_controller.dart`:
   - In `AppBar`, provide a reset/clear button (`Icons.restart_alt` or `Icons.delete_sweep_outlined`).
   - When tapped, show an `AlertDialog` confirming "Clear conversation history?".
   - On confirm, calls `ref.read(askControllerProvider.notifier).clearHistory()`, which resets state and wipes cached conversation history.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd app && flutter test test/ask_screen_test.dart`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/
git commit -m "feat(app): add starter chips, citation bottom sheet, and clear chat history"
```

---

### Task 8: Full End-to-End Verification & Web Wasm Build

**Files:**
- Verify: Entire repository (`api/`, `app/`, `eval/`)

**Interfaces:**
- Consumes: All updated API endpoints and Flutter widgets.
- Produces: Successful pytest suite, clean `flutter analyze`, green `flutter test`, and fresh compiled Web Wasm build in `app/build/web`.

- [ ] **Step 1: Run all backend tests**

Run: `docker compose exec api pytest -q`
Expected: 60+ passed, 0 failures

- [ ] **Step 2: Run Flutter analyzer**

Run: `cd app && flutter analyze`
Expected: 0 issues found

- [ ] **Step 3: Run all Flutter widget and unit tests**

Run: `cd app && flutter test`
Expected: All tests pass

- [ ] **Step 4: Rebuild Flutter Web Wasm**

Run: `cd app && flutter build web --wasm`
Expected: Web Wasm build succeeded in `app/build/web`

- [ ] **Step 5: Verify Docker container serves updated prototype**

Run: `docker exec swasthyastats-api-1 curl -s -I http://localhost:8000/`
Expected: HTTP 200 OK

- [ ] **Step 6: Log completion in progress.md and commit**

```bash
git add progress.md app/build/web
git commit -m "chore: complete PWA enhancements, offline caching, and review quick-add"
```
