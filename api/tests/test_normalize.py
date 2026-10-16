from app.pipeline.normalize import score_observations, ScoredObservation
from app.pipeline.extract import LabObservationRaw

OCR_LINES = [
    {"id": 1, "page": 1, "text": "Hemoglobin", "bbox": [0, 0, 100, 20], "conf": 0.96, "row_id": 1},
    {"id": 2, "page": 1, "text": "13.2", "bbox": [110, 0, 160, 20], "conf": 0.93, "row_id": 1},
]
LAB_DICT = {
    "hemoglobin": {
        "name": "Hemoglobin",
        "standard_unit": "g/dL",
        "plausible_range": [5.0, 25.0],
        "aliases": ["hgb", "hb"],
    }
}


def _obs(**kw) -> LabObservationRaw:
    defaults = dict(
        test_name="Hemoglobin",
        value=13.2,
        value_text=None,
        unit="g/dL",
        ref_low=12.0,
        ref_high=16.0,
        flag="normal",
        line_ids=[1, 2],
    )
    return LabObservationRaw(**(defaults | kw))


def test_grounding_passes_when_value_in_lines():
    results = score_observations([_obs()], OCR_LINES, LAB_DICT)
    assert len(results) == 1
    assert results[0].grounding_passed is True
    assert results[0].confidence > 0.8
    assert results[0].canonical_test_id == "hemoglobin"


def test_grounding_fails_when_value_not_in_lines():
    results = score_observations([_obs(value=99.9, line_ids=[1, 2])], OCR_LINES, LAB_DICT)
    assert len(results) == 1
    assert results[0].grounding_passed is False
    assert results[0].confidence < 0.6


def test_dictionary_match_sets_canonical_id_via_alias():
    obs = _obs(test_name="Total Hb", value=13.2, line_ids=[1, 2])
    # Extend dict with alias
    local_dict = {
        "hemoglobin": {
            "name": "Hemoglobin",
            "standard_unit": "g/dL",
            "plausible_range": [5.0, 25.0],
            "aliases": ["hgb", "hb", "total hb"],
        }
    }
    results = score_observations([obs], OCR_LINES, local_dict)
    assert results[0].canonical_test_id == "hemoglobin"
