import json
from unittest.mock import MagicMock
from app.pipeline.extract import (
    extract_page,
    recover_observations_from_ocr,
    LabReportRaw,
    ExtractionFailed,
)
from app.llm.client import LlmResponse


def _make_client(content: str) -> MagicMock:
    client = MagicMock()
    client.chat.return_value = LlmResponse(
        content=content,
        prompt_tokens=100,
        completion_tokens=50,
        latency_ms=200,
        model_used="test-model",
        key_label="k1",
    )
    return client


def test_extract_lab_report_with_doctor_name():
    from app.pipeline.extract import LabReportRaw, EXTRACTION_SYSTEM_PROMPT
    assert "doctor" in EXTRACTION_SYSTEM_PROMPT.lower()
    raw = LabReportRaw(lab_name="Central Lab", doctor_name="Dr. Jane Doe")
    assert raw.doctor_name == "Dr. Jane Doe"


def test_extract_page_happy_path():
    payload = {
        "lab_name": "City Lab",
        "report_date": "2026-10-01",
        "observations": [
            {
                "test_name": "Hemoglobin",
                "value": 13.2,
                "value_text": None,
                "unit": "g/dL",
                "ref_low": 12.0,
                "ref_high": 16.0,
                "flag": "normal",
                "line_ids": [1, 2],
            }
        ],
    }
    client = _make_client(json.dumps(payload))
    result = extract_page("Hemoglobin | 13.2 | g/dL", ocr_line_ids=[1, 2], client=client)
    assert isinstance(result, LabReportRaw)
    assert len(result.observations) == 1
    assert result.observations[0].test_name == "Hemoglobin"
    assert result.observations[0].value == 13.2
    assert result.observations[0].line_ids == [1, 2]


def test_extract_page_fallback_to_json_object():
    # Simulate first attempt failing or malformed markdown codeblock
    payload = {
        "lab_name": "Lab",
        "report_date": None,
        "observations": [
            {
                "test_name": "WBC",
                "value": 7500.0,
                "value_text": None,
                "unit": "/uL",
                "ref_low": 4000.0,
                "ref_high": 11000.0,
                "flag": "normal",
                "line_ids": [3],
            }
        ],
    }
    raw_markdown = f"```json\n{json.dumps(payload)}\n```"
    client = _make_client(raw_markdown)
    result = extract_page("WBC | 7500", ocr_line_ids=[3], client=client)
    assert len(result.observations) == 1
    assert result.observations[0].test_name == "WBC"


def test_extract_page_raises_on_all_failures():
    client = MagicMock()
    client.chat.side_effect = RuntimeError("All configured API keys are currently exhausted")
    try:
        extract_page("some text", ocr_line_ids=[1], client=client)
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass


def test_extract_page_raises_extraction_failed_on_invalid_json():
    client = _make_client("This is completely invalid non-JSON output")
    try:
        extract_page("some text", ocr_line_ids=[1], client=client)
        assert False, "Should have raised ExtractionFailed"
    except ExtractionFailed:
        pass


def test_recover_observations_from_page_two_ocr_when_llm_returns_empty():
    result = recover_observations_from_ocr(
        "[Line IDs: [69]]: PLATELET | 4,04,000 | /cumm\n"
        "[Line IDs: [70]]: COMMENT | correlate clinically",
        ocr_line_ids=[69, 70],
    )

    assert len(result) == 1
    assert result[0].test_name == "Platelet"
    assert result[0].value == 404000
    assert result[0].line_ids == [69]


def test_extract_page_chunks_large_ocr_and_aggregates_all_observations():
    def payload(start: int, end: int) -> str:
        return json.dumps(
            {
                "lab_name": "Lab",
                "report_date": None,
                "observations": [
                    {
                        "test_name": f"Test {index}",
                        "value": float(index),
                        "line_ids": [index],
                    }
                    for index in range(start, end + 1)
                ],
            }
        )

    client = MagicMock()
    client.chat.side_effect = [
        LlmResponse(
            content=payload(1, 6),
            prompt_tokens=100,
            completion_tokens=900,
            latency_ms=200,
            model_used="test-model",
            key_label="k1",
        ),
        LlmResponse(
            content=payload(7, 12),
            prompt_tokens=100,
            completion_tokens=900,
            latency_ms=200,
            model_used="test-model",
            key_label="k1",
        ),
    ]
    ocr = "\n".join(
        f"[Line IDs: [{index}]]: Test {index} | {index}"
        for index in range(1, 13)
    )

    result = extract_page(
        ocr,
        ocr_line_ids=list(range(1, 13)),
        client=client,
    )

    assert [observation.test_name for observation in result.observations] == [
        f"Test {index}" for index in range(1, 13)
    ]
    assert client.chat.call_count == 2
