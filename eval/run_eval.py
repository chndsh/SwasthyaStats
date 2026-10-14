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
    expected_num = ground_truth.get("numeric_tokens", [])
    expected_units = ground_truth.get("units", [])
    expected_rows = ground_truth.get("rows", [])

    num_found = sum(1 for tok in expected_num if tok in extracted_tokens or tok in extracted_text)
    num_acc = (num_found / len(expected_num)) if expected_num else 1.0

    unit_found = sum(1 for u in expected_units if u in extracted_units or u in extracted_text)
    unit_acc = (unit_found / len(expected_units)) if expected_units else 1.0

    row_found = sum(1 for r in expected_rows if r.strip() in extracted_text)
    row_acc = (row_found / len(expected_rows)) if expected_rows else 1.0

    return {
        "numeric_accuracy": round(float(num_acc), 4),
        "unit_accuracy": round(float(unit_acc), 4),
        "row_accuracy": round(float(row_acc), 4),
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

    # Append to eval/RESULTS.md
    results_md_path = "eval/RESULTS.md"
    with open(results_md_path, "a") as rf:
        rf.write(f"\n\n### OCR Benchmark Run\n\n")
        rf.write(f"| Sample | Numeric Accuracy | Unit Accuracy | Row Accuracy | Target Met |\n")
        rf.write(f"|---|---|---|---|---|\n")
        for fname, m in results_summary:
            target_met = "Yes" if m["numeric_accuracy"] >= 0.80 and m["row_accuracy"] >= 0.80 else "No"
            rf.write(f"| {fname} | {m['numeric_accuracy']*100:.1f}% | {m['unit_accuracy']*100:.1f}% | {m['row_accuracy']*100:.1f}% | {target_met} |\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate EasyOCR on sample documents.")
    parser.add_argument("--samples", default="eval/samples", help="Path to sample images")
    parser.add_argument("--ground-truth", default="eval/ground_truth", help="Path to ground truth JSONs")
    args = parser.parse_args()
    run_benchmark(args.samples, args.ground_truth)
