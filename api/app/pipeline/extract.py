import re
import json
import logging
from datetime import date
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ValidationError
from app.llm.client import OpenAICompatClient, LlmResponse

logger = logging.getLogger(__name__)


class ExtractionFailed(Exception):
    """Raised when LLM extraction parsing fails after retries."""
    pass


class LabObservationRaw(BaseModel):
    test_name: str
    value: Optional[float] = None
    value_text: Optional[str] = None
    unit: Optional[str] = None
    ref_low: Optional[float] = None
    ref_high: Optional[float] = None
    flag: Optional[Literal["low", "normal", "high", "critical"]] = None
    line_ids: List[int] = Field(default_factory=list)


class LabReportRaw(BaseModel):
    lab_name: Optional[str] = None
    report_date: Optional[date] = None
    observations: List[LabObservationRaw] = Field(default_factory=list)


EXTRACTION_SYSTEM_PROMPT = """You extract lab test results from OCR text of a medical lab report.
Return strictly valid JSON matching the schema.
Extract ALL lab test results and observations present in the text, do not omit any.
Each observation must reference the exact line_ids it was extracted from (found in [Line IDs: ...] prefixes or available line IDs).
Do not invent values or flags not supported by the text.
If a test result is non-numeric (e.g. Negative, Reactive, Absent), place it in value_text.
Otherwise place numeric numbers in value, and reference range numbers in ref_low / ref_high."""


def _clean_json_markdown(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def to_strict_json_schema(schema: dict) -> dict:
    """Ensures all object schemas have additionalProperties: false and required properties,

    satisfying OpenAI and Groq strict structured output requirements.
    """
    def _recurse(node):
        if not isinstance(node, dict):
            return
        if node.get("type") == "object" or "properties" in node:
            node["additionalProperties"] = False
            props = node.get("properties", {})
            if props:
                node["required"] = list(props.keys())
        for v in node.values():
            if isinstance(v, dict):
                _recurse(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _recurse(item)

    copied = json.loads(json.dumps(schema))
    _recurse(copied)
    return copied


def extract_page(
    redacted_text: str,
    ocr_line_ids: List[int],
    client: OpenAICompatClient,
    prompt_version: str = "v1",
) -> LabReportRaw:
    """Extracts lab observations from a single page of redacted OCR text.

    Retries on JSONDecodeError or schema mismatch before raising ExtractionFailed.
    Re-raises RuntimeError (e.g. key exhaustion) for the pipeline to catch.
    """
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"OCR Text:\n{redacted_text}\n\nAvailable OCR line IDs for this page: {ocr_line_ids}",
        },
    ]

    schema = to_strict_json_schema(LabReportRaw.model_json_schema())

    # Attempt 1: Default structured extraction
    last_error: Optional[Exception] = None
    for attempt in range(2):
        try:
            resp: LlmResponse = client.chat(
                messages,
                purpose="extract",
                json_schema=schema,
                temperature=0.0,
            )
            raw_text = _clean_json_markdown(resp.content)
            data = json.loads(raw_text)
            return LabReportRaw.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as err:
            last_error = err
            logger.warning(f"Extraction attempt {attempt + 1} parse error: {err}")

    # Attempt 2: Fallback with explicit JSON instructions
    try:
        fallback_messages = messages + [
            {
                "role": "user",
                "content": "Your previous response was not valid JSON matching the schema. Please return strictly valid raw JSON with keys 'lab_name', 'report_date', and 'observations'.",
            }
        ]
        resp = client.chat(
            fallback_messages,
            purpose="extract",
            json_schema=schema,
            temperature=0.0,
        )
        raw_text = _clean_json_markdown(resp.content)
        data = json.loads(raw_text)
        return LabReportRaw.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as err:
        raise ExtractionFailed(f"Could not parse extraction response after retries: {err}") from err
