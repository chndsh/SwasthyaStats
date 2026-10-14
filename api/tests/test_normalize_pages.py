import io
import pytest
from PIL import Image
from app.pipeline.normalize_pages import normalize_image, process_upload_to_pages, NormalizedPage


def test_normalize_image_resizes_and_converts_to_png():
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


def test_process_upload_to_pages_handles_image():
    img = Image.new("RGB", (800, 600), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    pages = process_upload_to_pages(buf.getvalue(), "test.png")

    assert len(pages) == 1
    assert isinstance(pages[0], NormalizedPage)
    assert pages[0].page_no == 1
    assert pages[0].width >= 2000 or pages[0].height >= 2000
    assert pages[0].image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
