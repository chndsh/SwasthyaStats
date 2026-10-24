import re
import json
import logging
from datetime import date
from typing import Dict, List, Optional, Literal, Sequence
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
    doctor_name: Optional[str] = None
    report_date: Optional[date] = None
    observations: List[LabObservationRaw] = Field(default_factory=list)


def recover_observations_from_ocr(
    redacted_text: str,
    ocr_line_ids: Sequence[int],
    known_test_names: Optional[Dict[str, str]] = None,
) -> List[LabObservationRaw]:
    """Recover only explicit, dictionary-backed result rows when extraction is empty."""
    known = known_test_names or {
        "platelet": "Platelet",
        "platelets": "Platelet",
        "plt": "Platelet",
    }
    aliases = {name.strip().lower(): label for name, label in known.items()}
    recovered: List[LabObservationRaw] = []
    line_pattern = re.compile(r"\[Line IDs:\s*\[([^\]]*)\]\]:\s*(.*)$", re.IGNORECASE)
    number_pattern = re.compile(r"^[+-]?\d[\d,]*(?:\.\d+)?$")
    qualitative_values = {
        "absent",
        "few",
        "many",
        "negative",
        "non-reactive",
        "normal",
        "positive",
        "present",
        "reactive",
    }

    for fallback_id, raw_line in zip(ocr_line_ids, redacted_text.splitlines()):
        match = line_pattern.match(raw_line.strip())
        if not match:
            continue
        line_ids = [
            int(value.strip())
            for value in match.group(1).split(",")
            if value.strip().isdigit()
        ] or [fallback_id]
        cells = [cell.strip() for cell in match.group(2).split("|")]
        if len(cells) < 2:
            continue
        test_name = aliases.get(cells[0].lower())
        if test_name is None:
            continue
        value_index = next(
            (
                index
                for index, cell in enumerate(cells[1:], start=1)
                if number_pattern.fullmatch(cell.replace(" ", ""))
            ),
            None,
        )
        if value_index is None:
            value_text = next(
                (
                    cell
                    for cell in cells[1:]
                    if cell.lower() in qualitative_values
                ),
                None,
            )
            if value_text is None:
                continue
            recovered.append(
                LabObservationRaw(
                    test_name=test_name,
                    value_text=value_text,
                    line_ids=line_ids,
                )
            )
            continue
        recovered.append(
            LabObservationRaw(
                test_name=test_name,
                value=float(cells[value_index].replace(",", "")),
                unit=cells[value_index + 1] if value_index + 1 < len(cells) else None,
                line_ids=line_ids,
            )
        )
    return recovered


EXTRACTION_SYSTEM_PROMPT = """You extract lab test results from OCR text of a medical lab report.
Return strictly valid JSON matching the schema.
Extract ALL genuine medical lab test results and observations present in the text, do not omit any.
If present in the report headers or metadata, extract the referring doctor or physician name into doctor_name, and the laboratory name into lab_name.
Each observation must reference the exact line_ids it was extracted from (found in [Line IDs: ...] prefixes or available line IDs).
CRITICAL RULES:
- NEVER extract units, column headers, reference range boundaries, or methods as test names (e.g. 'cumm', 'cells', 'HPF', 'Method', 'Unit', 'Ref. Range', 'Turbidimetric' are NOT tests).
- If a test name wraps across multiple words or lines, use the full test name (e.g. 'Platelet', 'Packed Cell Volume (PCV)').
- Do not invent values or flags not supported by the text.
- If a test result is non-numeric (e.g. Negative, Reactive, Absent), place it in value_text.
- Otherwise place numeric numbers in value, and reference range numbers in ref_low / ref_high."""


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
    known_test_names: Optional[Dict[str, str]] = None,
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
            report = LabReportRaw.model_validate(data)
            if not report.observations:
                report.observations = recover_observations_from_ocr(
                    redacted_text,
                    ocr_line_ids,
                    known_test_names,
                )
            return report
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
