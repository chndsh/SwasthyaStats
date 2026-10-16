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


def test_extraction_f1_calculation():
    from eval.run_eval import score_extraction

    ground_truth = {
        "rows": [
            "Hemoglobin | 13.5 | g/dL | 12.0 - 15.5",
            "Fasting Blood Sugar | 95.0 | mg/dL | 70.0 - 100.0",
        ]
    }
    predicted = [
        {"test_name": "Hemoglobin", "value_num": 13.5, "unit": "g/dL"},
        {"test_name": "Fasting Blood Sugar", "value_num": 95.0, "unit": "mg/dL"},
    ]
    res = score_extraction(predicted, ground_truth["rows"])
    assert res["precision"] == 1.0
    assert res["recall"] == 1.0
    assert res["f1"] == 1.0
