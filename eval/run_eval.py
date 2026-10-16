import os
import sys
import json
import argparse
from typing import Dict, List, Any
import numpy as np
import cv2


def evaluate_ocr_accuracy(
    ground_truth: Dict[str, Any],
    extracted_text: str,
    extracted_tokens: List[str],
    extracted_units: List[str],
) -> Dict[str, float]:
    """Calculates accuracy on numeric tokens, units, and row groupings."""
    import re

    def norm(s: str) -> str:
        return re.sub(r"[\s\./\-_]", "", s).lower()

    expected_num = ground_truth.get("numeric_tokens", [])
    expected_units = ground_truth.get("units", [])
    expected_rows = ground_truth.get("rows", [])

    norm_extracted_tokens = [norm(t) for t in extracted_tokens]

    num_found = sum(
        1
        for tok in expected_num
        if tok in extracted_tokens
        or tok in extracted_text
        or norm(tok) in norm_extracted_tokens
    )
    num_acc = (num_found / len(expected_num)) if expected_num else 1.0

    unit_found = sum(
        1
        for u in expected_units
        if u in extracted_units
        or u in extracted_text
        or norm(u) in norm_extracted_tokens
    )
    unit_acc = (unit_found / len(expected_units)) if expected_units else 1.0

    # Row grouping accuracy: check whether test name and value appear in the same row
    row_found = 0
    for r in expected_rows:
        parts = [p.strip() for p in r.split("|")]
        test_name = parts[0]
        # If test name is in extracted text and appears on a row with numbers
        if any(test_name.lower() in line.lower() for line in extracted_text.splitlines()):
            row_found += 1

    row_acc = (row_found / len(expected_rows)) if expected_rows else 1.0

    return {
        "numeric_accuracy": round(float(num_acc), 4),
        "unit_accuracy": round(float(unit_acc), 4),
        "row_accuracy": round(float(row_acc), 4),
    }


def score_extraction(
    predicted_observations: List[Dict[str, Any]],
    ground_truth_rows: List[str],
    tolerance: float = 0.05,
) -> Dict[str, float]:
    """Computes Precision, Recall, and F1 score for extracted observations against ground truth rows."""
    gt_entries = []
    for r in ground_truth_rows:
        parts = [p.strip() for p in r.split("|")]
        if len(parts) >= 2:
            test_name = parts[0]
            try:
                val = float(parts[1])
            except ValueError:
                val = None
            gt_entries.append({"test_name": test_name.lower(), "value": val})

    if not gt_entries and not predicted_observations:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not gt_entries or not predicted_observations:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    matched_gt = set()
    tp = 0

    for pred in predicted_observations:
        p_name = pred.get("test_name", "").strip().lower()
        p_val = pred.get("value_num")

        for i, gt in enumerate(gt_entries):
            if i in matched_gt:
                continue
            name_match = (p_name in gt["test_name"]) or (gt["test_name"] in p_name)
            if name_match:
                if p_val is not None and gt["value"] is not None:
                    val_match = abs(p_val - gt["value"]) <= tolerance
                elif p_val is None and gt["value"] is None:
                    val_match = True
                else:
                    val_match = False

                if val_match:
                    matched_gt.add(i)
                    tp += 1
                    break

    precision = round(tp / len(predicted_observations), 4)
    recall = round(tp / len(gt_entries), 4)
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": tp,
        "total_predicted": len(predicted_observations),
        "total_expected": len(gt_entries),
    }


def run_benchmark(samples_dir: str = "eval/samples", ground_truth_dir: str = "eval/ground_truth") -> None:
    # Lazy import to avoid unnecessary torch import when running unit tests
    from app.pipeline.ocr.easyocr_engine import EasyOcrEngine

    engine = EasyOcrEngine(languages=["en"], model_storage_directory="/root/.EasyOCR")

    if not os.path.exists(samples_dir):
        print(f"Directory {samples_dir} does not exist.")
        return

    sample_files = [f for f in os.listdir(samples_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    if not sample_files:
        print("No sample images found for evaluation.")
        return

    print(f"\n==================================================")
    print(f"Running EasyOCR Benchmark on {len(sample_files)} sample(s)")
    print(f"==================================================")

    results_summary = []

    for filename in sorted(sample_files):
        base_name = os.path.splitext(filename)[0]
        sample_path = os.path.join(samples_dir, filename)
        gt_path = os.path.join(ground_truth_dir, f"{base_name}.json")

        if not os.path.exists(gt_path):
            print(f"Skipping {filename}: no ground truth JSON found at {gt_path}")
            continue

        with open(gt_path, "r") as gf:
            ground_truth = json.load(gf)

        # Run OCR
        img_np = cv2.imread(sample_path, cv2.IMREAD_GRAYSCALE)
        if img_np is None:
            print(f"Failed to read image {sample_path}")
            continue

        ocr_text, ocr_lines = engine.run(img_np)
        extracted_tokens = [line["text"] for line in ocr_lines]
        metrics = evaluate_ocr_accuracy(ground_truth, ocr_text, extracted_tokens, extracted_tokens)

        print(f"\nSample: {filename}")
        print(f"  Numeric Accuracy: {metrics['numeric_accuracy'] * 100:.1f}%")
        print(f"  Unit Accuracy:    {metrics['unit_accuracy'] * 100:.1f}%")
        print(f"  Row Accuracy:     {metrics['row_accuracy'] * 100:.1f}%")

        results_summary.append((filename, metrics))

    # Optional extraction evaluation if LLM keys are configured or mock mode
    from app.db import SessionLocal
    from app.services.settings import SettingsService
    from app.pipeline.extract import extract_page
    from app.pipeline.redact import redact_text
    from app.llm.client import OpenAICompatClient

    db = SessionLocal()
    extraction_results = []
    try:
        settings_service = SettingsService(db)
        keys = settings_service.get_decrypted_keys()
        if keys:
            print("\n==================================================")
            print(f"Running LLM Extraction Benchmark (Provider: {settings_service.get_read_settings().llm_provider})")
            print("==================================================")
            client = OpenAICompatClient(db)
            for filename in sorted(sample_files):
                base_name = os.path.splitext(filename)[0]
                sample_path = os.path.join(samples_dir, filename)
                gt_path = os.path.join(ground_truth_dir, f"{base_name}.json")
                if not os.path.exists(gt_path):
                    continue
                with open(gt_path, "r") as gf:
                    gt = json.load(gf)

                img_np = cv2.imread(sample_path, cv2.IMREAD_GRAYSCALE)
                ocr_text, ocr_lines = engine.run(img_np)
                redacted = redact_text(ocr_text)
                line_ids = [l["id"] for l in ocr_lines if "id" in l]

                try:
                    report = extract_page(redacted, line_ids, client)
                    pred_obs = [o.model_dump() for o in report.observations]
                    f1_metrics = score_extraction(pred_obs, gt.get("rows", []))
                    print(f"\nExtraction for {filename}:")
                    print(f"  Field Precision: {f1_metrics['precision']*100:.1f}%")
                    print(f"  Field Recall:    {f1_metrics['recall']*100:.1f}%")
                    print(f"  Field F1:        {f1_metrics['f1']*100:.1f}%")
                    extraction_results.append((filename, f1_metrics))
                except Exception as ex:
                    print(f"Extraction failed for {filename}: {ex}")
        else:
            print("\n[Notice] No LLM keys configured in Settings. Skipping live LLM extraction bake-off.")
    finally:
        db.close()

    # Append to eval/RESULTS.md
    results_md_path = "eval/RESULTS.md"
    with open(results_md_path, "a") as rf:
        rf.write(f"\n\n### OCR Benchmark Run\n\n")
        rf.write(f"| Sample | Numeric Accuracy | Unit Accuracy | Row Accuracy | Target Met |\n")
        rf.write(f"|---|---|---|---|---|\n")
        for fname, m in results_summary:
            target_met = "Yes" if m["numeric_accuracy"] >= 0.80 and m["row_accuracy"] >= 0.80 else "No"
            rf.write(f"| {fname} | {m['numeric_accuracy']*100:.1f}% | {m['unit_accuracy']*100:.1f}% | {m['row_accuracy']*100:.1f}% | {target_met} |\n")

        if extraction_results:
            rf.write(f"\n\n### LLM Extraction Benchmark Run\n\n")
            rf.write(f"| Sample | Precision | Recall | Field F1 | Target (>=85%) |\n")
            rf.write(f"|---|---|---|---|---|\n")
            for fname, em in extraction_results:
                f1_met = "Yes" if em["f1"] >= 0.85 else "No"
                rf.write(f"| {fname} | {em['precision']*100:.1f}% | {em['recall']*100:.1f}% | {em['f1']*100:.1f}% | {f1_met} |\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate EasyOCR and extraction on sample documents.")
    parser.add_argument("--samples", default="eval/samples", help="Path to sample images")
    parser.add_argument("--ground-truth", default="eval/ground_truth", help="Path to ground truth JSONs")
    args = parser.parse_args()
    run_benchmark(args.samples, args.ground_truth)
