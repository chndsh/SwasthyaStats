from eval.run_eval import evaluate_ocr_accuracy


def test_eval_metrics_calculation():
    ground_truth = {
        "numeric_tokens": ["13.2", "12.0", "15.5"],
        "units": ["g/dL"],
        "rows": ["Hemoglobin | 13.2 | g/dL | 12.0-15.5"],
    }
    extracted_text = "Hemoglobin | 13.2 | g/dL | 12.0-15.5"
    extracted_tokens = ["13.2", "12.0", "15.5"]
    extracted_units = ["g/dL"]

    metrics = evaluate_ocr_accuracy(
        ground_truth, extracted_text, extracted_tokens, extracted_units
    )
    assert metrics["numeric_accuracy"] == 1.0
    assert metrics["unit_accuracy"] == 1.0
    assert metrics["row_accuracy"] == 1.0
