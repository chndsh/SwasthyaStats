import re
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from app.pipeline.extract import LabObservationRaw


@dataclass
class ScoredObservation:
    obs: LabObservationRaw
    canonical_test_id: Optional[str]
    normalized_unit: Optional[str]
    normalized_ref_low: Optional[float]
    normalized_ref_high: Optional[float]
    grounding_passed: bool
    confidence: float


def _find_canonical_test_id(test_name: str, lab_dictionary: Dict[str, Any]) -> Optional[str]:
    clean_name = test_name.strip().lower()

    # 1. Exact key match
    if clean_name in lab_dictionary:
        return clean_name

    # 2. Match against name or aliases in dictionary
    for canon_id, info in lab_dictionary.items():
        if clean_name == info.get("name", "").strip().lower():
            return canon_id
        for alias in info.get("aliases", []):
            if clean_name == alias.strip().lower():
                return canon_id

    # 3. Substring / word boundary fallback
    for canon_id, info in lab_dictionary.items():
        if canon_id in clean_name or info.get("name", "").strip().lower() in clean_name:
            return canon_id

    return None


def score_observations(
    raw_obs: List[LabObservationRaw],
    ocr_lines: List[Dict[str, Any]],
    lab_dictionary: Dict[str, Any],
) -> List[ScoredObservation]:
    """Applies grounding check against source OCR lines, normalizes against

    lab_dictionary, and computes a multi-factor confidence score (0.0 - 1.0).
    """
    lines_by_id = {line["id"]: line for line in ocr_lines if "id" in line}
    results: List[ScoredObservation] = []
    invalid_names = {
        "cells", "cumm", "hpf", "/hpf", "method", "unit", "ref range", "ref. range",
        "finding", "findings", "test name", "result", "turbidimetric"
    }

    for obs in raw_obs:
        clean_name = obs.test_name.strip().lower()
        if clean_name in invalid_names:
            continue

        # 1. Find referenced OCR lines
        referenced_lines = [lines_by_id[lid] for lid in obs.line_ids if lid in lines_by_id]
        if referenced_lines:
            ocr_conf = float(statistics.mean([l.get("conf", 0.7) for l in referenced_lines]))
            combined_text = " ".join([l.get("text", "") for l in referenced_lines])
        else:
            ocr_conf = 0.5
            combined_text = ""

        # 2. Grounding check
        grounding_passed = True
        if obs.value is not None:
            # Check if numeric value appears in referenced lines or anywhere in OCR lines
            val_str = f"{obs.value:.4g}"
            val_int_str = str(int(obs.value)) if obs.value.is_integer() else val_str

            in_ref = (val_str in combined_text) or (val_int_str in combined_text)
            if not in_ref:
                # Fallback: check if present anywhere in page's OCR lines
                all_page_text = " ".join([l.get("text", "") for l in ocr_lines])
                if (val_str not in all_page_text) and (val_int_str not in all_page_text):
                    grounding_passed = False

        grounding_score = 1.0 if grounding_passed else 0.0

        # 3. Dictionary lookup
        canon_id = _find_canonical_test_id(obs.test_name, lab_dictionary)
        dict_info = lab_dictionary.get(canon_id, {}) if canon_id else {}

        dict_match_score = 1.0 if canon_id else 0.6

        # 4. Unit validation
        std_unit = dict_info.get("standard_unit")
        normalized_unit = obs.unit
        if std_unit and obs.unit:
            clean_unit = obs.unit.strip().lower()
            clean_std = std_unit.strip().lower()
            if clean_unit == clean_std:
                unit_score = 1.0
                normalized_unit = std_unit
            else:
                unit_score = 0.5
        elif std_unit and not obs.unit:
            unit_score = 0.7
            normalized_unit = std_unit
        else:
            unit_score = 0.8

        # 5. Plausible range check
        plausible_range = dict_info.get("plausible_range")
        range_score = 1.0
        if plausible_range and obs.value is not None and len(plausible_range) == 2:
            p_min, p_max = plausible_range
            if obs.value < p_min or obs.value > p_max:
                range_score = 0.5

        # 6. Overall confidence calculation
        raw_conf = float(
            statistics.mean([
                ocr_conf,
                grounding_score,
                dict_match_score,
                unit_score,
                range_score,
            ])
        )
        # Grounding failure is a severe red flag; penalize overall confidence
        confidence = raw_conf if grounding_passed else min(raw_conf * 0.5, 0.45)

        results.append(
            ScoredObservation(
                obs=obs,
                canonical_test_id=canon_id,
                normalized_unit=normalized_unit,
                normalized_ref_low=obs.ref_low,
                normalized_ref_high=obs.ref_high,
                grounding_passed=grounding_passed,
                confidence=round(confidence, 3),
            )
        )

    return results
