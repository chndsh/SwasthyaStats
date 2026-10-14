import re
from typing import List, Tuple, Dict, Any
import numpy as np
from app.pipeline.ocr.base import OcrBox


def _is_numeric(text: str) -> bool:
    """Returns True if text consists predominantly of numbers and numeric symbols."""
    clean = re.sub(r"[\s\.,<>\-/%]", "", text)
    return clean.isdigit() if clean else False


def reconstruct_rows(boxes: List[OcrBox], page_no: int = 1) -> Tuple[str, List[Dict[str, Any]]]:
    """Clusters boxes into rows with tolerance ≈ 0.5 × median height, applies

    heuristic to merge vertically adjacent test-name cells, and returns
    (ocr_text, ocr_lines).
    """
    if not boxes:
        return "", []

    # 1. Compute median height
    median_h = float(np.median([b.height for b in boxes]))
    tolerance = max(8.0, 0.5 * median_h)

    # 2. Sort by y_center
    sorted_boxes = sorted(boxes, key=lambda b: b.y_center)

    # 3. Initial clustering into rows
    rows: List[List[OcrBox]] = []
    row_y_centers: List[float] = []

    for b in sorted_boxes:
        placed = False
        for r_idx, r_y in enumerate(row_y_centers):
            if abs(b.y_center - r_y) <= tolerance:
                rows[r_idx].append(b)
                # Recalculate row center
                row_y_centers[r_idx] = float(np.mean([item.y_center for item in rows[r_idx]]))
                placed = True
                break
        if not placed:
            rows.append([b])
            row_y_centers.append(b.y_center)

    # Sort rows by their average y_center
    row_tuples = sorted(zip(row_y_centers, rows), key=lambda t: t[0])
    rows = [r for _, r in row_tuples]

    # Sort boxes in each row by x_left
    for r in rows:
        r.sort(key=lambda b: b.x_left)

    # 4. Vertical test-name cell merge heuristic
    # Check consecutive rows where column 1 text is vertically adjacent and wraps
    merged_rows: List[List[OcrBox]] = []
    skip_next = False

    for i in range(len(rows)):
        if skip_next:
            skip_next = False
            continue

        curr_row = rows[i]
        if i + 1 < len(rows):
            next_row = rows[i + 1]
            box_curr = curr_row[0]
            box_next = next_row[0]

            # Conditions for vertical test-name header merge:
            # 1. Both are mostly text (not pure numbers)
            # 2. Left edges are aligned (abs(x_left diff) < 60)
            # 3. Vertical distance between them is close (<= 2.5 * median_h)
            # 4. At least one row has only 1 box (or curr_row has the title continuation)
            is_text_curr = not _is_numeric(box_curr.text)
            is_text_next = not _is_numeric(box_next.text)
            x_aligned = abs(box_curr.x_left - box_next.x_left) < 60
            y_close = (box_next.y_center - box_curr.y_center) <= (2.5 * median_h)

            if is_text_curr and is_text_next and x_aligned and y_close:
                # If current row is just the header prefix (e.g. "Total")
                # and next row has the rest (e.g. "Cholesterol", "195", "mg/dL")
                # OR next row is just the header suffix
                if len(curr_row) == 1 or len(next_row) == 1:
                    merged_box = OcrBox(
                        text=f"{box_curr.text.strip()} {box_next.text.strip()}",
                        bbox=[
                            [min(box_curr.bbox[0][0], box_next.bbox[0][0]), min(box_curr.bbox[0][1], box_next.bbox[0][1])],
                            [max(box_curr.bbox[1][0], box_next.bbox[1][0]), min(box_curr.bbox[1][1], box_next.bbox[1][1])],
                            [max(box_curr.bbox[2][0], box_next.bbox[2][0]), max(box_curr.bbox[2][1], box_next.bbox[2][1])],
                            [min(box_curr.bbox[3][0], box_next.bbox[3][0]), max(box_curr.bbox[3][1], box_next.bbox[3][1])],
                        ],
                        conf=float(np.mean([box_curr.conf, box_next.conf])),
                        y_center=float(np.mean([box_curr.y_center, box_next.y_center])),
                        height=box_curr.height + box_next.height,
                        x_left=min(box_curr.x_left, box_next.x_left),
                    )
                    other_boxes = [b for b in curr_row[1:]] + [b for b in next_row[1:]]
                    other_boxes.sort(key=lambda b: b.x_left)
                    combined_row = [merged_box] + other_boxes
                    merged_rows.append(combined_row)
                    skip_next = True
                    continue

        merged_rows.append(curr_row)

    # 5. Format pipe-delimited text and ocr_lines
    ocr_lines: List[Dict[str, Any]] = []
    text_lines: List[str] = []
    line_id = 1

    for row_id, r in enumerate(merged_rows, start=1):
        row_cells = [b.text.strip() for b in r if b.text.strip()]
        if not row_cells:
            continue
        text_lines.append(" | ".join(row_cells))

        for b in r:
            x_min = int(min(pt[0] for pt in b.bbox))
            y_min = int(min(pt[1] for pt in b.bbox))
            x_max = int(max(pt[0] for pt in b.bbox))
            y_max = int(max(pt[1] for pt in b.bbox))
            ocr_lines.append(
                {
                    "id": line_id,
                    "page": page_no,
                    "text": b.text.strip(),
                    "bbox": [x_min, y_min, x_max, y_max],
                    "conf": round(float(b.conf), 4),
                    "row_id": row_id,
                }
            )
            line_id += 1

    full_text = "\n".join(text_lines)
    return full_text, ocr_lines
