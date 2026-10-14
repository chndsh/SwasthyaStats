import io
import math
from dataclasses import dataclass
from typing import List, Tuple
from PIL import Image, ImageOps
import cv2
import numpy as np
import pypdfium2 as pdfium


@dataclass
class NormalizedPage:
    page_no: int
    image_bytes: bytes
    width: int
    height: int


def _deskew(image_gray: np.ndarray) -> np.ndarray:
    """Deskews grayscale image if slight tilt is detected."""
    # Invert image: text becomes white, background black
    thresh = cv2.threshold(image_gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 50:
        return image_gray

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    elif angle > 45:
        angle = 90 - angle
    else:
        angle = -angle

    # Only correct mild skew (between 0.5 and 15 degrees)
    if abs(angle) < 0.5 or abs(angle) > 15.0:
        return image_gray

    (h, w) = image_gray.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image_gray,
        m,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,
    )
    return rotated


def normalize_image(image_bytes: bytes) -> Tuple[bytes, int, int]:
    """Applies EXIF rotation, deskew, grayscale, CLAHE, and resize (long side 2000-2500px).

    Returns (png_bytes, width, height).
    """
    if not image_bytes:
        raise ValueError("Empty image bytes")

    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        raise ValueError(f"Invalid image format: {e}")

    # 1. EXIF orientation correction
    pil_img = ImageOps.exif_transpose(pil_img)

    # 2. Convert to RGB then OpenCV grayscale
    if pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")
    np_img = np.array(pil_img)
    gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)

    # 3. Deskew
    gray = _deskew(gray)

    # 4. Mild contrast adjustment (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # 5. Resize: target long side between 2000 and 2500 px
    h, w = gray.shape[:2]
    long_side = max(h, w)
    target_long = 2500 if long_side > 2500 else (2000 if long_side < 2000 else long_side)

    if target_long != long_side:
        scale = target_long / float(long_side)
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        gray = cv2.resize(gray, (new_w, new_h), interpolation=interp)
        h, w = new_h, new_w

    # 6. Encode to PNG
    success, encoded = cv2.imencode(".png", gray)
    if not success:
        raise RuntimeError("Failed to encode normalized image to PNG")

    return encoded.tobytes(), w, h


def process_upload_to_pages(file_bytes: bytes, filename: str) -> List[NormalizedPage]:
    """Splits PDF or processes image bytes, normalizes each page, returns list of NormalizedPage."""
    if not file_bytes:
        raise ValueError("Empty file")

    is_pdf = filename.lower().endswith(".pdf") or file_bytes.startswith(b"%PDF")
    pages: List[NormalizedPage] = []

    if is_pdf:
        try:
            pdf = pdfium.PdfDocument(file_bytes)
        except Exception as e:
            raise ValueError(f"Corrupted or invalid PDF file: {e}")

        total_pages = len(pdf)
        if total_pages == 0:
            raise ValueError("PDF contains no pages")
        if total_pages > 10:
            raise ValueError("Document exceeds maximum page limit of 10 pages")

        for idx in range(total_pages):
            page = pdf[idx]
            # Render page at 300 DPI for high-quality OCR (standard PDF 72pt = 1 inch)
            pil_image = page.render(scale=300 / 72).to_pil()
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            png_bytes, width, height = normalize_image(buf.getvalue())
            pages.append(
                NormalizedPage(
                    page_no=idx + 1,
                    image_bytes=png_bytes,
                    width=width,
                    height=height,
                )
            )
    else:
        png_bytes, width, height = normalize_image(file_bytes)
        pages.append(
            NormalizedPage(
                page_no=1,
                image_bytes=png_bytes,
                width=width,
                height=height,
            )
        )

    return pages
