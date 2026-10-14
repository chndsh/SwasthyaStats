# Week 2: Capture and OCR Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete Week 2 document capture, multi-page image/PDF normalization, EasyOCR engine, row reconstruction with wrapped header merging, background async processing, REST API endpoints, evaluation benchmark, and Flutter capture UI.

**Architecture:** A multi-page image/PDF ingestion pipeline that normalizes documents using OpenCV and `pypdfium2` (EXIF orientation, grayscale, CLAHE, resizing to 2000-2500px long side) into standard page images. An OCR layer wrapping EasyOCR with median-height row clustering, vertically adjacent test cell merging, and pipe-delimited output. A FastAPI background worker persisting status transitions (`queued` -> `normalizing` -> `ocr` -> `needs_review`) and serving page images and lines, coupled with a responsive Flutter Web Wasm client for camera/file picking and document inspection.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL (pgvector), OpenCV (headless), PyTorch CPU, EasyOCR, pypdfium2, Pillow, Flutter Web (Wasm), pytest, respx.

---

### Task 1: Image & PDF Normalization Service

**Files:**
- Create: `api/app/services/image_processing.py`
- Test: `api/tests/test_image_processing.py`

**Step 1: Write the failing test**

```python
# api/tests/test_image_processing.py
import io
import numpy as np
from PIL import Image
from app.services.image_processing import normalize_image_bytes, split_and_normalize_document

def test_normalize_image_bytes():
    # Create simple 100x200 RGB test image
    img = Image.new("RGB", (100, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()

    normalized_bytes, width, height = normalize_image_bytes(raw_bytes, target_max_dim=2200)
    assert isinstance(normalized_bytes, bytes)
    assert len(normalized_bytes) > 0
    # Long edge scaled towards target_max_dim (or preserved if small)
    assert width > 0 and height > 0
    assert max(width, height) <= 2200

def test_split_and_normalize_document_image():
    img = Image.new("RGB", (300, 400), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    pages = split_and_normalize_document("test.png", raw_bytes)
    assert len(pages) == 1
    page_no, norm_bytes, w, h = pages[0]
    assert page_no == 1
    assert w > 0 and h > 0
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_image_processing.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.image_processing'`

**Step 3: Write minimal implementation**

```python
# api/app/services/image_processing.py
import io
import cv2
import numpy as np
from PIL import Image, ImageOps
import pypdfium2 as pdfium


def normalize_cv2_image(cv_img: np.ndarray, target_max_dim: int = 2200) -> tuple[np.ndarray, int, int]:
    # 1. Grayscale if color
    if len(cv_img.shape) == 3:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cv_img

    # 2. Mild contrast enhancement (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 3. Resize long edge to ~2000-2500 px
    h, w = enhanced.shape[:2]
    long_side = max(h, w)
    if long_side > target_max_dim:
        scale = target_max_dim / float(long_side)
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        resized = cv2.resize(enhanced, (new_w, new_h), interpolation=cv2.INTER_AREA)
    else:
        resized = enhanced
        new_w, new_h = w, h

    return resized, new_w, new_h


def normalize_image_bytes(raw_bytes: bytes, target_max_dim: int = 2200) -> tuple[bytes, int, int]:
    # Use PIL to safely handle EXIF rotation
    pil_img = Image.open(io.BytesIO(raw_bytes))
    pil_img = ImageOps.exif_transpose(pil_img)

    # Convert to RGB numpy array for OpenCV
    rgb_arr = np.array(pil_img.convert("RGB"))
    bgr_arr = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)

    normalized_cv, w, h = normalize_cv2_image(bgr_arr, target_max_dim=target_max_dim)

    # Encode as PNG bytes
    success, encoded = cv2.imencode(".png", normalized_cv)
    if not success:
        raise ValueError("Failed to encode normalized image to PNG")
    return encoded.tobytes(), w, h


def split_and_normalize_document(filename: str, file_bytes: bytes) -> list[tuple[int, bytes, int, int]]:
    """
    Given a filename and raw bytes (PDF or image), returns list of:
    (page_no, normalized_png_bytes, width, height)
    """
    is_pdf = filename.lower().endswith(".pdf") or file_bytes.startswith(b"%PDF")
    results = []

    if is_pdf:
        pdf = pdfium.PdfDocument(file_bytes)
        for i in range(len(pdf)):
            page = pdf.get_page(i)
            # Render page at 300 DPI (scale ~4.16x standard 72 DPI)
            bitmap = page.render(scale=3.0)
            pil_image = bitmap.to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            norm_bytes, w, h = normalize_image_bytes(buf.getvalue())
            results.append((i + 1, norm_bytes, w, h))
    else:
        norm_bytes, w, h = normalize_image_bytes(file_bytes)
        results.append((1, norm_bytes, w, h))

    return results
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_image_processing.py`
Expected: PASS with 2 passed

**Step 5: Commit**

```bash
git add api/app/services/image_processing.py api/tests/test_image_processing.py
git commit -m "feat(ocr): add image and PDF normalization service"
```

---

### Task 2: OCR Row Reconstruction and Cell Merging

**Files:**
- Create: `api/app/ocr/schemas.py`
- Create: `api/app/ocr/reconstruct.py`
- Test: `api/tests/test_ocr_reconstruct.py`

**Step 1: Write the failing test**

```python
# api/tests/test_ocr_reconstruct.py
from app.ocr.schemas import RawOcrBox, OcrLine
from app.ocr.reconstruct import reconstruct_rows

def test_reconstruct_rows_simple():
    # Two words on row 1, two words on row 2
    boxes = [
        RawOcrBox(text="Hemoglobin", bbox=[[10, 10], [100, 10], [100, 30], [10, 30]], conf=0.95),
        RawOcrBox(text="14.2", bbox=[150, 10], [200, 10], [200, 30], [150, 30]], conf=0.92),
        RawOcrBox(text="WBC", bbox=[[10, 50], [60, 50], [60, 70], [10, 70]], conf=0.98),
        RawOcrBox(text="6500", bbox=[150, 50], [210, 50], [210, 70], [150, 70]], conf=0.91),
    ]
    lines, text = reconstruct_rows(boxes, page_no=1)
    assert len(lines) == 2
    assert "Hemoglobin | 14.2" in text
    assert "WBC | 6500" in text

def test_reconstruct_rows_vertical_header_merge():
    # Multi-line wrapped test header: "Total" on row 1, "Cholesterol" directly beneath on row 2
    boxes = [
        RawOcrBox(text="Total", bbox=[[10, 10], [80, 10], [80, 30], [10, 30]], conf=0.9),
        RawOcrBox(text="Cholesterol", bbox=[[10, 35], [120, 35], [120, 55], [10, 55]], conf=0.9),
        RawOcrBox(text="190", bbox=[200, 35], [240, 35], [240, 55], [200, 55]], conf=0.95),
    ]
    lines, text = reconstruct_rows(boxes, page_no=1)
    assert "Total Cholesterol | 190" in text
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ocr_reconstruct.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ocr.schemas'`

**Step 3: Write minimal implementation**

```python
# api/app/ocr/schemas.py
from pydantic import BaseModel, Field

class RawOcrBox(BaseModel):
    text: str
    bbox: list[list[float]]  # 4 polygon points: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
    conf: float

    @property
    def x_min(self) -> float:
        return min(pt[0] for pt in self.bbox)

    @property
    def x_max(self) -> float:
        return max(pt[0] for pt in self.bbox)

    @property
    def y_min(self) -> float:
        return min(pt[1] for pt in self.bbox)

    @property
    def y_max(self) -> float:
        return max(pt[1] for pt in self.bbox)

    @property
    def y_center(self) -> float:
        return (self.y_min + self.y_max) / 2.0

    @property
    def height(self) -> float:
        return max(1.0, self.y_max - self.y_min)


class OcrLine(BaseModel):
    id: int
    page: int
    text: str
    bbox: list[float]  # [x_min, y_min, x_max, y_max] bounding rect
    conf: float
    row_id: int
```

```python
# api/app/ocr/reconstruct.py
import statistics
from typing import List, Tuple
from app.ocr.schemas import RawOcrBox, OcrLine


def reconstruct_rows(
    boxes: List[RawOcrBox],
    page_no: int = 1,
    start_line_id: int = 1
) -> Tuple[List[OcrLine], str]:
    if not boxes:
        return [], ""

    # Sort primarily by y_center
    sorted_boxes = sorted(boxes, key=lambda b: (b.y_center, b.x_min))

    median_height = statistics.median([b.height for b in sorted_boxes])
    y_tolerance = max(8.0, median_height * 0.5)

    # Cluster into rows
    rows: List[List[RawOcrBox]] = []
    for box in sorted_boxes:
        placed = False
        for row in rows:
            row_y_center = statistics.mean([b.y_center for b in row])
            if abs(box.y_center - row_y_center) <= y_tolerance:
                row.append(box)
                placed = True
                break
        if not placed:
            rows.append([box])

    # Sort cells within each row by x_min
    for row in rows:
        row.sort(key=lambda b: b.x_min)

    # Vertical merge heuristic: detect multi-line test headers
    # If a row has only one text cell on the left, and row below starts at similar x, merge them
    merged_rows: List[List[RawOcrBox]] = []
    skip_next = False
    for i in range(len(rows)):
        if skip_next:
            skip_next = False
            continue

        curr_row = rows[i]
        if i + 1 < len(rows):
            next_row = rows[i + 1]
            # If current row is a single non-numeric word on the left (<35% width of page)
            if len(curr_row) == 1 and not any(ch.isdigit() for ch in curr_row[0].text):
                first_curr = curr_row[0]
                first_next = next_row[0]
                # If horizontally aligned (x_min diff < 40px) and close vertically
                if abs(first_curr.x_min - first_next.x_min) < 40 and (first_next.y_min - first_curr.y_max) < median_height * 1.5:
                    merged_box = RawOcrBox(
                        text=f"{first_curr.text} {first_next.text}",
                        bbox=[
                            [min(first_curr.x_min, first_next.x_min), first_curr.y_min],
                            [max(first_curr.x_max, first_next.x_max), first_curr.y_min],
                            [max(first_curr.x_max, first_next.x_max), first_next.y_max],
                            [min(first_curr.x_min, first_next.x_min), first_next.y_max],
                        ],
                        conf=(first_curr.conf + first_next.conf) / 2.0,
                    )
                    combined_row = [merged_box] + next_row[1:]
                    merged_rows.append(combined_row)
                    skip_next = True
                    continue

        merged_rows.append(curr_row)

    # Format OcrLines and pipe-delimited text
    ocr_lines: List[OcrLine] = []
    row_strings: List[str] = []
    line_counter = start_line_id

    for row_idx, row in enumerate(merged_rows, start=1):
        row_text = " | ".join(b.text.strip() for b in row if b.text.strip())
        if not row_text:
            continue
        row_strings.append(row_text)

        for cell in row:
            ocr_lines.append(
                OcrLine(
                    id=line_counter,
                    page=page_no,
                    text=cell.text.strip(),
                    bbox=[round(cell.x_min, 1), round(cell.y_min, 1), round(cell.x_max, 1), round(cell.y_max, 1)],
                    conf=round(float(cell.conf), 3),
                    row_id=row_idx,
                )
            )
            line_counter += 1

    return ocr_lines, "\n".join(row_strings)
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_ocr_reconstruct.py`
Expected: PASS with 2 passed

**Step 5: Commit**

```bash
git add api/app/ocr/schemas.py api/app/ocr/reconstruct.py api/tests/test_ocr_reconstruct.py
git commit -m "feat(ocr): add row clustering and vertical cell reconstruction"
```

---

### Task 3: EasyOCR Engine Integration

**Files:**
- Create: `api/app/ocr/engine.py`
- Test: `api/tests/test_ocr_engine.py`

**Step 1: Write the failing test**

```python
# api/tests/test_ocr_engine.py
import numpy as np
from unittest.mock import MagicMock, patch
from app.ocr.engine import EasyOcrEngine

def test_ocr_engine_protocol_with_mock():
    # Mock EasyOCR Reader to avoid downloading weights during fast unit tests
    engine = EasyOcrEngine(languages=["en"], gpu=False)
    fake_reader = MagicMock()
    fake_reader.readtext.return_value = [
        ([[10, 10], [50, 10], [50, 30], [10, 30]], "Glucose", 0.96),
        ([[100, 10], [140, 10], [140, 30], [100, 30]], "95", 0.94),
    ]
    engine._reader = fake_reader

    dummy_image = np.zeros((100, 200), dtype=np.uint8)
    ocr_lines, ocr_text = engine.run(dummy_image, page_no=1)

    assert len(ocr_lines) == 2
    assert "Glucose | 95" in ocr_text
    assert ocr_lines[0].text == "Glucose"
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_ocr_engine.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.ocr.engine'`

**Step 3: Write minimal implementation**

```python
# api/app/ocr/engine.py
from typing import List, Protocol, Tuple
import numpy as np
import easyocr
from app.ocr.schemas import RawOcrBox, OcrLine
from app.ocr.reconstruct import reconstruct_rows


class OcrEngine(Protocol):
    def run(self, image: np.ndarray, page_no: int = 1) -> Tuple[List[OcrLine], str]:
        ...


class EasyOcrEngine:
    def __init__(
        self,
        languages: list[str] | None = None,
        gpu: bool = False,
        model_storage_directory: str = "/root/.EasyOCR",
    ):
        self.languages = languages or ["en"]
        self.gpu = gpu
        self.model_storage_directory = model_storage_directory
        self._reader: easyocr.Reader | None = None

    @property
    def reader(self) -> easyocr.Reader:
        if self._reader is None:
            self._reader = easyocr.Reader(
                self.languages,
                gpu=self.gpu,
                model_storage_directory=self.model_storage_directory,
                download_enabled=True,
            )
        return self._reader

    def run(
        self,
        image: np.ndarray,
        page_no: int = 1,
        mag_ratio: float = 1.0,
        text_threshold: float = 0.6,
        low_text: float = 0.3,
        link_threshold: float = 0.4,
    ) -> Tuple[List[OcrLine], str]:
        results = self.reader.readtext(
            image,
            detail=1,
            paragraph=False,
            mag_ratio=mag_ratio,
            text_threshold=text_threshold,
            low_text=low_text,
            link_threshold=link_threshold,
        )

        boxes: List[RawOcrBox] = []
        for bbox, text, conf in results:
            if not text.strip():
                continue
            boxes.append(RawOcrBox(text=text.strip(), bbox=bbox, conf=float(conf)))

        return reconstruct_rows(boxes, page_no=page_no)
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_ocr_engine.py`
Expected: PASS with 1 passed

**Step 5: Commit**

```bash
git add api/app/ocr/engine.py api/tests/test_ocr_engine.py
git commit -m "feat(ocr): add EasyOcrEngine implementation"
```

---

### Task 4: Document Service and Background Processing Pipeline

**Files:**
- Create: `api/app/services/documents.py`
- Test: `api/tests/test_document_service.py`

**Step 1: Write the failing test**

```python
# api/tests/test_document_service.py
import pytest
from app.db import SessionLocal
from app.models import Patient, Document
from app.services.documents import create_document, process_document_pipeline

def test_create_and_process_document(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    db = SessionLocal()
    try:
        patient = db.query(Patient).first()
        if not patient:
            patient = Patient(name="Test Patient")
            db.add(patient)
            db.commit()

        # Create dummy PNG file
        raw_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR..."
        doc = create_document(
            db=db,
            patient_id=patient.id,
            filename="report.pdf",
            file_bytes=raw_bytes,
        )
        assert doc.id is not None
        assert doc.status == "queued"
    finally:
        db.close()
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_document_service.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.documents'`

**Step 3: Write minimal implementation**

```python
# api/app/services/documents.py
import hashlib
import os
import cv2
import numpy as np
from sqlalchemy.orm import Session
from app.config import get_settings
from app.models import Document, DocumentPage
from app.services.image_processing import split_and_normalize_document
from app.ocr.engine import EasyOcrEngine

_ocr_engine = None

def get_ocr_engine() -> EasyOcrEngine:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = EasyOcrEngine()
    return _ocr_engine


def create_document(
    db: Session,
    patient_id: int,
    filename: str,
    file_bytes: bytes,
) -> Document:
    settings = get_settings()
    os.makedirs(settings.storage_path, exist_ok=True)

    file_sha256 = hashlib.sha256(file_bytes).hexdigest()
    orig_path = os.path.join(settings.storage_path, f"{file_sha256}_{filename}")
    with open(orig_path, "wb") as f:
        f.write(file_bytes)

    doc = Document(
        patient_id=patient_id,
        filename=filename,
        sha256=file_sha256,
        status="queued",
        doc_type="lab_report",
        page_count=1,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def process_document_pipeline(document_id: int, db: Session) -> None:
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        return

    try:
        # Step 1: Normalizing
        doc.status = "normalizing"
        db.commit()

        settings = get_settings()
        orig_file = os.path.join(settings.storage_path, f"{doc.sha256}_{doc.filename}")
        with open(orig_file, "rb") as f:
            raw_bytes = f.read()

        pages = split_and_normalize_document(doc.filename, raw_bytes)
        doc.page_count = len(pages)

        # Clear existing pages if re-running
        db.query(DocumentPage).filter(DocumentPage.document_id == doc.id).delete()

        page_records = []
        for page_no, norm_bytes, w, h in pages:
            page_rel_path = f"doc_{doc.id}_p{page_no}.png"
            page_abs_path = os.path.join(settings.storage_path, page_rel_path)
            with open(page_abs_path, "wb") as f:
                f.write(norm_bytes)

            page_rec = DocumentPage(
                document_id=doc.id,
                page_no=page_no,
                width=w,
                height=h,
                image_path=page_abs_path,
                original_path=orig_file,
            )
            db.add(page_rec)
            page_records.append((page_rec, page_abs_path, page_no))

        db.commit()

        # Step 2: OCR
        doc.status = "ocr"
        db.commit()

        engine = get_ocr_engine()
        all_lines = []
        all_text_sections = []

        for page_rec, page_path, page_no in page_records:
            cv_img = cv2.imread(page_path, cv2.IMREAD_GRAYSCALE)
            lines, text = engine.run(cv_img, page_no=page_no)
            all_lines.extend([l.model_dump() for l in lines])
            all_text_sections.append(f"--- PAGE {page_no} ---\n{text}")

        doc.ocr_lines = all_lines
        doc.ocr_text = "\n\n".join(all_text_sections)
        # Advance to needs_review (or extracting in Week 3)
        doc.status = "needs_review"
        db.commit()

    except Exception as e:
        db.rollback()
        doc.status = "failed"
        db.commit()
        raise e
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_document_service.py`
Expected: PASS with 1 passed

**Step 5: Commit**

```bash
git add api/app/services/documents.py api/tests/test_document_service.py
git commit -m "feat(documents): add document storage and background processing service"
```

---

### Task 5: Document REST Endpoints

**Files:**
- Create: `api/app/routers/documents.py`
- Modify: `api/app/main.py:1-40`
- Test: `api/tests/test_document_endpoints.py`

**Step 1: Write the failing test**

```python
# api/tests/test_document_endpoints.py
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_document_endpoints_unauthorized():
    res = client.get("/api/v1/documents")
    assert res.status_code == 401

def test_document_upload_and_status():
    file_content = b"%PDF-1.4 test dummy"
    files = {"files": ("report.pdf", io.BytesIO(file_content), "application/pdf")}
    res = client.post(
        "/api/v1/documents",
        headers={"X-API-Key": "change-me"},
        files=files,
    )
    assert res.status_code == 202
    data = res.json()
    assert "document_id" in data
    doc_id = data["document_id"]

    res_get = client.get(f"/api/v1/documents/{doc_id}", headers={"X-API-Key": "change-me"})
    assert res_get.status_code == 200
    assert res_get.json()["id"] == doc_id
```

**Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_document_endpoints.py`
Expected: FAIL with 404 Not Found for `/api/v1/documents`

**Step 3: Write minimal implementation**

```python
# api/app/routers/documents.py
import os
from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Patient, Document, DocumentPage
from app.security.auth import get_api_key
from app.services.documents import create_document, process_document_pipeline

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(get_api_key)])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    patient = db.query(Patient).first()
    if not patient:
        patient = Patient(name="Default Patient")
        db.add(patient)
        db.commit()
        db.refresh(patient)

    # If single PDF or single image:
    first_file = files[0]
    content = await first_file.read()
    doc = create_document(db, patient.id, first_file.filename or "uploaded_doc", content)

    background_tasks.add_task(process_document_pipeline, doc.id, db)
    return {"document_id": doc.id, "status": doc.status}


@router.get("")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.created_at.desc()).limit(50).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "status": d.status,
            "page_count": d.page_count,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "page_count": doc.page_count,
        "ocr_lines": doc.ocr_lines or [],
        "ocr_text": doc.ocr_text or "",
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.get("/{document_id}/pages/{page_no}.png")
def get_page_image(document_id: int, page_no: int, db: Session = Depends(get_db)):
    page = (
        db.query(DocumentPage)
        .filter(DocumentPage.document_id == document_id, DocumentPage.page_no == page_no)
        .first()
    )
    if not page or not os.path.exists(page.image_path):
        raise HTTPException(status_code=404, detail="Page image not found")
    return FileResponse(page.image_path, media_type="image/png")
```

Include `router` in `api/app/main.py`:
```python
from app.routers import settings, documents
app.include_router(documents.router, prefix="/api/v1")
```

**Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_document_endpoints.py`
Expected: PASS with 2 passed

**Step 5: Commit**

```bash
git add api/app/routers/documents.py api/app/main.py api/tests/test_document_endpoints.py
git commit -m "feat(api): add document upload and page retrieval endpoints"
```

---

### Task 6: Evaluation Benchmark and Bake-off Script

**Files:**
- Create: `eval/run_eval.py`
- Create: `eval/test_eval.py`

**Step 1: Write the failing test**

```python
# eval/test_eval.py
from run_eval import calculate_cer, calculate_wer

def test_cer_wer_metrics():
    ground_truth = "Hemoglobin 14.2 g/dL"
    hypothesis = "Hemoglobin 14.2 g/dL"
    assert calculate_cer(ground_truth, hypothesis) == 0.0
    assert calculate_wer(ground_truth, hypothesis) == 0.0

    bad_hyp = "Hemoglobin 14.0 g/dL"
    assert calculate_cer(ground_truth, bad_hyp) > 0.0
    assert calculate_wer(ground_truth, bad_hyp) > 0.0
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=eval pytest eval/test_eval.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'run_eval'`

**Step 3: Write minimal implementation**

```python
# eval/run_eval.py
import sys

def levenshtein_distance(s1: str, s2: str) -> int:
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n]


def calculate_cer(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    dist = levenshtein_distance(reference, hypothesis)
    return dist / len(reference)


def calculate_wer(reference: str, hypothesis: str) -> float:
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    if not ref_words:
        return 0.0 if not hyp_words else 1.0
    # Levenshtein at word level
    m, n = len(ref_words), len(hyp_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
    return dp[m][n] / len(ref_words)


if __name__ == "__main__":
    print("OCR Benchmark Evaluation Tool ready.")
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=eval pytest eval/test_eval.py`
Expected: PASS with 1 passed

**Step 5: Commit**

```bash
git add eval/run_eval.py eval/test_eval.py
git commit -m "feat(eval): add OCR CER/WER benchmark scoring script"
```

---

### Task 7: Flutter PWA Capture and Document Viewer Screen

**Files:**
- Create: `app/lib/features/capture/capture_screen.dart`
- Create: `app/lib/features/documents/document_detail_screen.dart`
- Modify: `app/lib/main.dart`
- Test: `app/test/document_test.dart`

**Step 1: Write the failing test**

```dart
// app/test/document_test.dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:swasthya_stats/features/capture/capture_screen.dart';

void main() {
  testWidgets('CaptureScreen displays upload buttons', (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: CaptureScreen(),
      ),
    );

    expect(find.text('Upload Report'), findsOneWidget);
    expect(find.byIcon(Icons.camera_alt), findsOneWidget);
  });
}
```

**Step 2: Run test to verify it fails**

Run: `cd app && flutter test test/document_test.dart`
Expected: FAIL with compilation error: `capture_screen.dart` does not exist

**Step 3: Write minimal implementation**

Create `app/lib/features/capture/capture_screen.dart` with image/PDF selection, upload progress indicator, and batch pick support.
Create `app/lib/features/documents/document_detail_screen.dart` with responsive split view (image on left/top, OCR rows on right/bottom) fetching `/api/v1/documents/{id}/pages/{n}.png` via `dio` and showing bounding boxes or reconstructed text.
Link screens in `app/lib/main.dart` navigation routes (`/#/capture`, `/#/documents`).

**Step 4: Run test to verify it passes**

Run: `cd app && flutter test`
Expected: PASS with all tests passing

**Step 5: Commit**

```bash
git add app/lib/ app/test/
git commit -m "feat(ui): add report capture and document detail viewer"
```

---

### Plan Execution Handoff

Plan complete and saved to `docs/plans/2026-10-14-week-2-capture-ocr.md`. Two execution options:

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration.
2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints.

Which approach?
