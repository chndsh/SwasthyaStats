from dataclasses import dataclass, field
from typing import List, Protocol
import numpy as np


@dataclass
class OcrBox:
    text: str
    bbox: List[List[int]]  # [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    conf: float
    y_center: float
    height: float
    x_left: float


@dataclass
class OcrLine:
    id: int
    page: int
    text: str
    bbox: List[int]  # [x_min, y_min, x_max, y_max]
    conf: float
    row_id: int


class OcrEngine(Protocol):
    def run(self, image_np: np.ndarray, page_no: int = 1) -> tuple[str, list[dict]]:
        ...
