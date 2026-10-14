import os
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import easyocr
from app.pipeline.ocr.base import OcrBox, OcrEngine
from app.pipeline.ocr.rows import reconstruct_rows


class EasyOcrEngine(OcrEngine):
    def __init__(
        self,
        languages: Optional[List[str]] = None,
        model_storage_directory: str = "/root/.EasyOCR",
        gpu: bool = False,
    ):
        self.languages = languages or ["en"]
        self.model_storage_directory = model_storage_directory
        os.makedirs(self.model_storage_directory, exist_ok=True)
        self.reader = easyocr.Reader(
            self.languages,
            gpu=gpu,
            model_storage_directory=self.model_storage_directory,
            download_enabled=True,
        )

    def run(self, image_np: np.ndarray, page_no: int = 1) -> Tuple[str, List[Dict[str, Any]]]:
        """Runs EasyOCR text detection and recognition on image array,

        then reconstructs pipe-delimited table rows.
        """
        raw_detections = self.reader.readtext(image_np, detail=1, paragraph=False)
        boxes: List[OcrBox] = []

        for bbox, text, conf in raw_detections:
            if not text.strip():
                continue
            y_pts = [pt[1] for pt in bbox]
            x_pts = [pt[0] for pt in bbox]
            y_center = float(np.mean(y_pts))
            height = float(max(y_pts) - min(y_pts))
            x_left = float(min(x_pts))

            boxes.append(
                OcrBox(
                    text=text.strip(),
                    bbox=[[int(pt[0]), int(pt[1])] for pt in bbox],
                    conf=float(conf),
                    y_center=y_center,
                    height=max(height, 5.0),
                    x_left=x_left,
                )
            )

        return reconstruct_rows(boxes, page_no=page_no)
