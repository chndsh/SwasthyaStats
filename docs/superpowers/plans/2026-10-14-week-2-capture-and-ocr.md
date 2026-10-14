# Week 2: Capture, Normalization, EasyOCR Engine, and Document Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the end-to-end Week 2 milestone: multi-page image/PDF document capture and upload, image normalization, EasyOCR table row reconstruction with vertical test cell merging, background processing lifecycle, page-image serving, Flutter PWA capture UI, and OCR evaluation harness.

**Architecture:** A FastAPI ingestion endpoint receives multi-page photos or PDFs, triggers an asynchronous background pipeline that normalizes pages (EXIF, deskew, CLAHE, resizing via OpenCV/Pillow/pypdfium2), runs EasyOCR with row clustering and vertical test header merging, and stores normalized images and reconstructed pipe-delimited OCR lines in PostgreSQL. A responsive Flutter Web PWA interface enables native camera capture, batch image/PDF picking, document list status polling, and page inspection.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, pypdfium2, OpenCV (opencv-python-headless), Pillow, EasyOCR, PyTorch CPU, Flutter Web (Wasm), Riverpod, Dio, ImagePicker, FilePicker.

**Spec:** [prototype-architecture.md](file:///home/chandish/Documents/SwasthyaStats/prototype-architecture.md#L633-L638) (Sections 6, 7.3, 9, 10.1, 13, 14, 15, 16, 17)

## Global Constraints

- Wasm compilation (`--wasm`) is the primary build target for Flutter Web.
- All code must be open source (Apache 2.0 / MIT / BSD / PostgreSQL). Avoid PyMuPDF (AGPL).
- Models (EasyOCR) are cached dynamically in persistent named volume (`/root/.EasyOCR`).
- Multi-page upload limit: maximum 12 MB per file, maximum 10 pages per document.
- Page normalization target: long side resized to 2000–2500 px, EXIF orientation corrected, grayscale, CLAHE contrast applied, deskewed.
- Normalized page images are saved to disk (`STORAGE_PATH / documents / {document_id} / pages / {page_no}.png`) and served via `GET /api/v1/documents/{id}/pages/{n}.png`.
- Table row reconstruction clusters boxes with tolerance ≈ 0.5 × median box height, applies vertical test-name cell merge heuristic, and formats lines with ` | ` pipe delimiters.
- Document status lifecycle: `queued` → `normalizing` → `ocr` → `needs_review` (or `failed`).
- All API routes require `X-API-Key` header authentication.

## Review Focus

1. Corrupted or invalid upload file (non-image or broken PDF bytes): must reject immediately with `400 Bad Request` before persisting database records (tested in Task 3).
2. Multi-line test name wrapping across vertical rows: row reconstruction merge heuristic must combine multi-line labels before pipe emission without joining numeric values (tested in Task 2).
3. Oversized upload (> 12 MB or > 10 pages): must return `413 Payload Too Large` or `400 Bad Request` with exact page count error (tested in Task 3).
4. Rotated phone photos with EXIF tags: normalization must auto-orient according to EXIF and output upright 2000-2500px images (tested in Task 1).
5. Transient OCR failure on corrupted page image: document status must transition to `failed` and log the error without crashing background worker (tested in Task 3).

---

### Task 1: Page Normalization and Image Service

**Files:**
- Create: `api/app/pipeline/normalize_pages.py`
- Test: `api/tests/test_normalize_pages.py`

**Interfaces:**
- Consumes: `pypdfium2`, `PIL.Image`, `cv2`, `numpy`
- Produces:
  ```python
  class NormalizedPage:
      page_no: int
      image_bytes: bytes  # PNG bytes
      width: int
      height: int

  def normalize_image(image_bytes: bytes) -> tuple[bytes, int, int]:
      """Applies EXIF rotation, deskew, grayscale, CLAHE, and resize (long side 2000-2500px). Returns (png_bytes, width, height)."""

  def process_upload_to_pages(file_bytes: bytes, filename: str) -> list[NormalizedPage]:
      """Splits PDF or takes image bytes, normalizes each page, returns list of NormalizedPage."""
  ```

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_normalize_pages.py`:
```python
import io
import pytest
from PIL import Image
from app.pipeline.normalize_pages import normalize_image, process_upload_to_pages

def test_normalize_image_resizes_and_converts_to_png():
    # Create small test image
    img = Image.new("RGB", (3000, 1500), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()

    png_bytes, width, height = normalize_image(raw_bytes)

    assert width == 2500 or height == 2500
    assert width <= 2500 and height <= 2500
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

def test_process_upload_to_pages_rejects_empty():
    with pytest.raises(ValueError, match="Empty file"):
        process_upload_to_pages(b"", "empty.png")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_normalize_pages.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError (`app.pipeline.normalize_pages`)

- [ ] **Step 3: Implement `normalize_pages.py`**

Create `api/app/pipeline/normalize_pages.py`:
- Use `PIL.ImageOps.exif_transpose` for EXIF orientation.
- Deskew via OpenCV minAreaRect on binary thresholded image.
- Convert to grayscale and apply CLAHE (`cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))`).
- Resize with aspect ratio preserved so max(width, height) is between 2000 and 2500 px.
- For PDF files, use `pypdfium2.PdfDocument(file_bytes)` to render each page at 300 DPI into PIL image, then normalize.
- Validate page count <= 10, raise `ValueError("Document exceeds maximum page limit of 10 pages")` if exceeded.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_normalize_pages.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/pipeline/normalize_pages.py api/tests/test_normalize_pages.py
git commit -m "feat(pipeline): add page normalization and pdf splitting"
```

---

### Task 2: EasyOCR Engine and Table Row Reconstruction

**Files:**
- Create: `api/app/pipeline/ocr/base.py`
- Create: `api/app/pipeline/ocr/rows.py`
- Create: `api/app/pipeline/ocr/easyocr_engine.py`
- Test: `api/tests/test_ocr_reconstruction.py`

**Interfaces:**
- Consumes: Normalized page image (`np.ndarray` or bytes)
- Produces:
  ```python
  @dataclass
  class OcrBox:
      text: str
      bbox: list[list[int]]  # [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
      conf: float
      y_center: float
      height: float
      x_left: float

  @dataclass
  class OcrLine:
      id: int
      page: int
      text: str
      bbox: list[int]  # [x_min, y_min, x_max, y_max]
      conf: float
      row_id: int

  def reconstruct_rows(boxes: list[OcrBox], page_no: int = 1) -> tuple[str, list[dict]]:
      """Clusters boxes into rows (0.5 * median height), applies vertical test-name merge heuristic, returns (ocr_text, ocr_lines)."""

  class EasyOcrEngine:
      def __init__(self, languages: list[str] = ["en"], model_storage_directory: str = "/root/.EasyOCR"): ...
      def run(self, image_np: np.ndarray, page_no: int = 1) -> tuple[str, list[dict]]: ...
  ```

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_ocr_reconstruction.py`:
```python
from app.pipeline.ocr.base import OcrBox
from app.pipeline.ocr.rows import reconstruct_rows

def test_row_reconstruction_clusters_and_merges_vertical_headers():
    # Box 1 & 2: Multi-line test name "Total\nCholesterol" stacked vertically in column 1
    box1 = OcrBox(text="Total", bbox=[[50, 100], [150, 100], [150, 120], [50, 120]], conf=0.95, y_center=110, height=20, x_left=50)
    box2 = OcrBox(text="Cholesterol", bbox=[[50, 125], [200, 125], [200, 145], [50, 145]], conf=0.95, y_center=135, height=20, x_left=50)
    # Box 3: Value in column 2 aligned with the row
    box3 = OcrBox(text="195", bbox=[[300, 120], [350, 120], [350, 140], [300, 140]], conf=0.98, y_center=130, height=20, x_left=300)
    # Box 4: Unit in column 3
    box4 = OcrBox(text="mg/dL", bbox=[[400, 120], [480, 120], [480, 140], [400, 140]], conf=0.94, y_center=130, height=20, x_left=400)

    ocr_text, ocr_lines = reconstruct_rows([box1, box2, box3, box4], page_no=1)

    assert "Total Cholesterol | 195 | mg/dL" in ocr_text
    assert len(ocr_lines) >= 1
    assert ocr_lines[0]["page"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ocr_reconstruction.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'app.pipeline.ocr'

- [ ] **Step 3: Implement `base.py`, `rows.py`, and `easyocr_engine.py`**

- `api/app/pipeline/ocr/base.py`: Define `OcrBox` and `OcrLine` dataclasses.
- `api/app/pipeline/ocr/rows.py`:
  - Calculate median height across boxes.
  - Cluster into rows using threshold `0.5 * median_height`.
  - Heuristic for vertically adjacent test-name cells: check consecutive row clusters where column 1 contains purely alphabetical text with horizontal overlap and no intervening numeric values; merge these headers into a single row before joining with ` | `.
  - Format output: sort boxes by `x_left`, join with ` | `, construct `ocr_lines` list matching schema (`id`, `page`, `text`, `bbox`, `conf`, `row_id`).
- `api/app/pipeline/ocr/easyocr_engine.py`:
  - Initialize `easyocr.Reader(languages, gpu=False, model_storage_directory=model_dir)`.
  - `run()` calls `readtext(image_np, detail=1, paragraph=False)`, converts detections to `OcrBox`, and delegates to `reconstruct_rows`.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_ocr_reconstruction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/pipeline/ocr/
git commit -m "feat(ocr): add EasyOCR engine and table row reconstruction"
```

---

### Task 3: Document Ingestion, Background Processing, and API Endpoints

**Files:**
- Create: `api/app/services/documents.py`
- Create: `api/app/routers/documents.py`
- Modify: `api/app/main.py:40-45`
- Modify: `api/app/schemas.py:90-103`
- Test: `api/tests/test_documents_api.py`

**Interfaces:**
- Consumes: `app.pipeline.normalize_pages`, `app.pipeline.ocr.easyocr_engine`, `app.models.Document`, `app.models.DocumentPage`
- Produces:
  ```python
  # API Endpoints:
  POST /api/v1/documents (multipart upload 1..n files or 1 PDF) -> 202 {id, status, page_count}
  GET  /api/v1/documents -> list of {id, filename, status, page_count, created_at}
  GET  /api/v1/documents/{id} -> {id, filename, status, page_count, created_at, pages: [...]}
  GET  /api/v1/documents/{id}/pages/{page_no}.png -> image/png streaming response
  ```

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_documents_api.py`:
```python
import io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app

client = TestClient(app)
AUTH_HEADER = {"X-API-Key": "change-me"}

def test_upload_document_creates_queued_doc_and_streams_page():
    img = Image.new("RGB", (1000, 800), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # 1. Upload
    response = client.post(
        "/api/v1/documents",
        headers=AUTH_HEADER,
        files=[("files", ("test_page.png", buf.getvalue(), "image/png"))]
    )
    assert response.status_code == 202
    data = response.json()
    doc_id = data["id"]
    assert data["status"] in ["queued", "normalizing", "ocr", "needs_review"]

    # 2. Get document details
    doc_resp = client.get(f"/api/v1/documents/{doc_id}", headers=AUTH_HEADER)
    assert doc_resp.status_code == 200
    assert doc_resp.json()["filename"] == "test_page.png"

def test_upload_rejects_empty_file():
    response = client.post(
        "/api/v1/documents",
        headers=AUTH_HEADER,
        files=[("files", ("empty.png", b"", "image/png"))]
    )
    assert response.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_documents_api.py -v`
Expected: FAIL with 404 (Route not found: `/api/v1/documents`)

- [ ] **Step 3: Implement Document Service, Router, and mount in `main.py`**

- Create `api/app/services/documents.py`:
  - `create_document_and_save_upload(files, db)`: Validates total size <= 12 MB, page count <= 10. Computes SHA256. Creates `Document(status="queued")`.
  - `process_document_background(doc_id, file_payloads)`:
    - Sets `status = "normalizing"`. Calls `process_upload_to_pages`.
    - Persists normalized images to `{STORAGE_PATH}/documents/{doc_id}/pages/{page_no}.png` and creates `DocumentPage` records.
    - Sets `status = "ocr"`. Runs `EasyOcrEngine().run()` on each page image.
    - Concatenates page text and `ocr_lines`, updates `Document(ocr_text=..., ocr_lines=..., status="needs_review")`.
    - Catch exceptions and set `status = "failed"` with logged reason.
- Create `api/app/routers/documents.py`:
  - `POST /documents`: Enqueues `BackgroundTasks`, returns 202.
  - `GET /documents`: Returns all documents for active patient.
  - `GET /documents/{id}`: Returns document details and page metadata.
  - `GET /documents/{id}/pages/{page_no}.png`: Reads file from disk, returns `Response(content=img_bytes, media_type="image/png")`.
- Mount router in `api/app/main.py`: `app.include_router(documents_router.router)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_documents_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/app/services/documents.py api/app/routers/documents.py api/app/main.py api/tests/test_documents_api.py
git commit -m "feat(api): document upload, background OCR processing, and page streaming"
```

---

### Task 4: Evaluation Benchmark Harness (`eval/run_eval.py`)

**Files:**
- Create: `eval/run_eval.py`
- Create: `eval/samples/sample_lab_report.png`
- Create: `eval/ground_truth/sample_lab_report.json`
- Create: `eval/RESULTS.md`
- Test: `api/tests/test_eval_harness.py`

**Interfaces:**
- Consumes: Sample images and ground truth JSON files (`expected_tokens`, `expected_units`, `expected_rows`)
- Produces: CLI execution printing accuracy metrics (% character, % numeric token, % unit, % rows correctly grouped) and appending summary to `eval/RESULTS.md`.

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_eval_harness.py`:
```python
from eval.run_eval import evaluate_ocr_accuracy

def test_eval_metrics_calculation():
    ground_truth = {
        "numeric_tokens": ["13.2", "12.0", "15.5"],
        "units": ["g/dL"],
        "rows": ["Hemoglobin | 13.2 | g/dL | 12.0-15.5"]
    }
    extracted_text = "Hemoglobin | 13.2 | g/dL | 12.0-15.5"
    extracted_tokens = ["13.2", "12.0", "15.5"]
    extracted_units = ["g/dL"]

    metrics = evaluate_ocr_accuracy(ground_truth, extracted_text, extracted_tokens, extracted_units)
    assert metrics["numeric_accuracy"] == 1.0
    assert metrics["unit_accuracy"] == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_eval_harness.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'eval'

- [ ] **Step 3: Implement evaluation script and sample ground truth**

- Create `eval/run_eval.py` with `evaluate_ocr_accuracy()` function and `main()` CLI accepting `--samples-dir` and `--ground-truth-dir`.
- Create synthetic lab report image `eval/samples/sample_lab_report.png` (using PIL with standard lab fonts: Test Name, Value, Unit, Ref Range).
- Create corresponding `eval/ground_truth/sample_lab_report.json`.
- Initialize `eval/RESULTS.md` with table matching prototype architecture Section 15 & 16.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_eval_harness.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add eval/ api/tests/test_eval_harness.py
git commit -m "feat(eval): add OCR evaluation harness, sample test report, and ground truth"
```

---

### Task 5: Flutter PWA Documents List, Camera Capture, Batch Picker, and Page Viewer

**Files:**
- Create: `app/lib/features/documents/document_model.dart`
- Create: `app/lib/features/documents/documents_controller.dart`
- Create: `app/lib/features/documents/documents_screen.dart`
- Create: `app/lib/features/documents/document_view_screen.dart`
- Modify: `app/lib/features/navigation/app_router.dart:156-173`
- Test: `app/test/documents_screen_test.dart`

**Interfaces:**
- Consumes: `/api/v1/documents`, `/api/v1/documents/{id}/pages/{n}.png` via `ApiClient`
- Produces:
  - Responsive Documents screen with document status chips (`queued`, `normalizing`, `ocr`, `needs_review`, `failed`).
  - Capture modal: Camera capture with multi-page loop + batch file/image picker.
  - Page inspection view with pan/zoom (`InteractiveViewer`) and `Image.memory` (retrieved over Dio with API key).

- [ ] **Step 1: Write the failing test**

Create `app/test/documents_screen_test.dart`:
```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:app/features/documents/documents_screen.dart';
import 'package:app/features/documents/documents_controller.dart';
import 'package:app/features/documents/document_model.dart';

class FakeDocumentsController extends DocumentsController {
  @override
  Future<List<DocumentItem>> build() async {
    return [
      DocumentItem(id: 1, filename: "cbc_report.pdf", status: "needs_review", pageCount: 2, createdAt: DateTime.now()),
      DocumentItem(id: 2, filename: "lipid_panel.png", status: "ocr", pageCount: 1, createdAt: DateTime.now()),
    ];
  }
}

void main() {
  testWidgets('DocumentsScreen displays documents and status chips', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          documentsControllerProvider.overrideWith(() => FakeDocumentsController()),
        ],
        child: const MaterialApp(home: DocumentsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('cbc_report.pdf'), findsOneWidget);
    expect(find.text('needs_review'), findsOneWidget);
    expect(find.text('lipid_panel.png'), findsOneWidget);
    expect(find.byIcon(Icons.add), findsOneWidget);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `flutter test test/documents_screen_test.dart`
Expected: FAIL with compilation error (Target of URI hasn't been generated: `documents_screen.dart`)

- [ ] **Step 3: Implement Documents models, controller, screen, and viewer**

- `app/lib/features/documents/document_model.dart`: Data model `DocumentItem` with `id`, `filename`, `status`, `pageCount`, `createdAt`.
- `app/lib/features/documents/documents_controller.dart`: `AsyncNotifier<List<DocumentItem>>` fetching `/documents` via `ApiClient`, polling every 3 seconds if any document is in `queued`, `normalizing`, or `ocr` status. Upload method supporting multi-image and PDF upload.
- `app/lib/features/documents/documents_screen.dart`: List view with status badges, pull-to-refresh, Floating Action Button opening bottom sheet with "Take Photo (Camera)" and "Upload Files/PDF".
- `app/lib/features/documents/document_view_screen.dart`: Shows page selector and normalized page image fetched with `dio.get<List<int>>(..., responseType: ResponseType.bytes)` and rendered in `InteractiveViewer` with `Image.memory`.
- Update `app_router.dart` to link `/documents` to `DocumentsScreen` and `/documents/:id` to `DocumentViewScreen`.

- [ ] **Step 4: Run test to verify it passes**

Run: `flutter test test/documents_screen_test.dart`
Expected: PASS

- [ ] **Step 5: Verify Flutter Web Wasm build**

Run: `cd app && flutter build web --wasm --release --dart-define=API_BASE=/api/v1`
Expected: Build succeeds with output in `app/build/web`.

- [ ] **Step 6: Commit**

```bash
git add app/lib/features/documents/ app/lib/features/navigation/app_router.dart app/test/documents_screen_test.dart
git commit -m "feat(pwa): documents screen with camera capture, batch picker, and page viewer"
```

---

### Task 6: End-to-End Integration Verification & Progress Logging

**Files:**
- Modify: `progress.md`
- Test: Full integration test suite

- [ ] **Step 1: Run complete backend test suite in Docker**

Run: `docker compose exec -T api pytest -v`
Expected: All tests pass (including crypto, LLM client, normalize pages, OCR rows, documents API, and eval harness).

- [ ] **Step 2: Run complete Flutter test suite**

Run: `cd app && flutter test`
Expected: All tests pass.

- [ ] **Step 3: Run OCR evaluation benchmark on sample report**

Run: `docker compose exec -T api python eval/run_eval.py`
Expected: Evaluates sample report and writes results to `eval/RESULTS.md`.

- [ ] **Step 4: Update `progress.md`**

Update `progress.md` with:
- Task: Week 2 - Capture, Normalization, EasyOCR Engine, and Document Processing.
- Decisions made, changes summary, verification results, and status = Completed.

- [ ] **Step 5: Commit**

```bash
git add progress.md eval/RESULTS.md
git commit -m "docs: complete week 2 capture and OCR milestone with evaluation results"
```
