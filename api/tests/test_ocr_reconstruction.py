from app.pipeline.ocr.base import OcrBox
from app.pipeline.ocr.rows import reconstruct_rows


def test_row_reconstruction_clusters_and_merges_vertical_headers():
    # Box 1 & 2: Multi-line test name "Total\nCholesterol" stacked vertically in column 1
    box1 = OcrBox(
        text="Total",
        bbox=[[50, 100], [150, 100], [150, 120], [50, 120]],
        conf=0.95,
        y_center=110,
        height=20,
        x_left=50,
    )
    box2 = OcrBox(
        text="Cholesterol",
        bbox=[[50, 125], [200, 125], [200, 145], [50, 145]],
        conf=0.95,
        y_center=135,
        height=20,
        x_left=50,
    )
    # Box 3: Value in column 2 aligned with the row
    box3 = OcrBox(
        text="195",
        bbox=[[300, 120], [350, 120], [350, 140], [300, 140]],
        conf=0.98,
        y_center=130,
        height=20,
        x_left=300,
    )
    # Box 4: Unit in column 3
    box4 = OcrBox(
        text="mg/dL",
        bbox=[[400, 120], [480, 120], [480, 140], [400, 140]],
        conf=0.94,
        y_center=130,
        height=20,
        x_left=400,
    )

    ocr_text, ocr_lines = reconstruct_rows([box1, box2, box3, box4], page_no=1)

    assert "Total Cholesterol | 195 | mg/dL" in ocr_text
    assert len(ocr_lines) >= 1
    assert ocr_lines[0]["page"] == 1
    assert "row_id" in ocr_lines[0]
