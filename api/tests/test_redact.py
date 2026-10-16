from app.pipeline.redact import redact_text


def test_patient_name_masked():
    result = redact_text("Patient: Ram Bahadur\nHemoglobin 13.2", patient_name="Ram Bahadur")
    assert "[PATIENT]" in result
    assert "Ram Bahadur" not in result
    assert "Hemoglobin" in result   # medical term preserved
    assert "13.2" in result


def test_standard_pii_masked():
    result = redact_text("DOB: 1985-03-14, Phone: 9841012345, Email: user@example.com")
    assert "1985-03-14" not in result
    assert "9841012345" not in result
    assert "user@example.com" not in result
    assert "[DOB]" in result
    assert "[PHONE]" in result
    assert "[EMAIL]" in result


def test_lab_values_not_masked():
    text = "Glucose | 95 | mg/dL | 70–110"
    result = redact_text(text)
    assert result == text  # nothing masked
