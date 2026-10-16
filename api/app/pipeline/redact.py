import re
from typing import Optional


def redact_text(text: str, patient_name: Optional[str] = None) -> str:
    """Non-aggressive PII redaction anchored to patient name and explicit headers,

    preserving medical terms, test names, values, units, and ranges.
    """
    if not text:
        return ""

    redacted = text

    # 1. Mask explicit patient name if provided
    if patient_name and patient_name.strip():
        name_pattern = re.compile(rf"\b{re.escape(patient_name.strip())}\b", re.IGNORECASE)
        redacted = name_pattern.sub("[PATIENT]", redacted)

    # 2. Mask name after common header labels like 'Name:', 'Patient Name:', 'Patient:'
    redacted = re.sub(
        r"(?i)\b(patient(?:\s+name)?|name)\s*:\s*([A-Za-z\.\s]+?)(?=(\n|\r|,|\||\s{2,}|$))",
        r"\1: [PATIENT]",
        redacted,
    )

    # 3. Mask DOB / Date of Birth
    redacted = re.sub(
        r"(?i)\b(dob|date\s+of\s+birth)\s*:\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        r"\1: [DOB]",
        redacted,
    )

    # 4. Mask Email addresses
    redacted = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "[EMAIL]",
        redacted,
    )

    # 5. Mask Phone numbers (e.g. 10-digit mobile numbers or phone header)
    redacted = re.sub(
        r"(?i)\b(phone|mobile|tel|contact)\s*:\s*(\+?\d[\d\s-]{7,}\d)",
        r"\1: [PHONE]",
        redacted,
    )
    redacted = re.sub(
        r"(?<![\d\.-])(\+?977[- ]?)?[98]\d{9}(?![\d\.-])",
        "[PHONE]",
        redacted,
    )

    # 6. Mask National / ID numbers (Citizenship, Passport, etc.)
    redacted = re.sub(
        r"(?i)\b(citizenship|nid|national\s*id|passport|ssn)\s*(?:no\.?|number)?\s*:\s*([A-Za-z0-9\-/]+)",
        r"\1: [ID]",
        redacted,
    )

    return redacted
