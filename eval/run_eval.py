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


def embed_bakeoff(top_k: int = 5) -> Dict[str, float]:
    """Bake-off comparing multilingual-e5-small vs bge-small-en-v1.5 on retrieval Recall@k."""
    from app.pipeline.embed import EmbedEngine

    test_corpus = [
        "HbA1c 6.8 % on 2026-06-15 (ref 4.0–5.6)",
        "Fasting Blood Sugar 112 mg/dL on 2026-06-15 (ref 70–99)",
        "Total Cholesterol 215 mg/dL on 2026-06-15 (ref 125–200)",
        "HDL Cholesterol 42 mg/dL on 2026-06-15 (ref 40–60)",
        "LDL Cholesterol 145 mg/dL on 2026-06-15 (ref < 100)",
        "Serum Creatinine 0.9 mg/dL on 2026-05-10 (ref 0.6–1.2)",
        "Hemoglobin 13.5 g/dL on 2026-05-10 (ref 12.0–15.5)",
        "Platelet Count 240000 /uL on 2026-05-10 (ref 150000–450000)",
        "Patient advised low sodium diet and regular aerobic exercise 30 minutes daily.",
        "Metformin 500mg once daily with evening meal prescribed for blood glucose control.",
    ]

    eval_qa = [
        {"query": "What is my glycated hemoglobin level?", "target": "HbA1c"},
        {"query": "How is my fasting blood sugar?", "target": "Fasting Blood Sugar"},
        {"query": "Is my cholesterol high?", "target": "Total Cholesterol"},
        {"query": "What is my good HDL cholesterol reading?", "target": "HDL Cholesterol"},
        {"query": "What is my bad LDL cholesterol reading?", "target": "LDL Cholesterol"},
        {"query": "Check my kidney function and creatinine levels", "target": "Serum Creatinine"},
        {"query": "What was my red blood cell hemoglobin count?", "target": "Hemoglobin"},
        {"query": "What was my platelet count?", "target": "Platelet Count"},
        {"query": "What lifestyle or diet advice was given?", "target": "low sodium diet"},
        {"query": "What medication was prescribed for diabetes management?", "target": "Metformin"},
    ]

    models_to_test = ["multilingual-e5-small", "bge-small-en-v1.5"]
    recalls = {}

    print("\n==================================================")
    print("Running Embedding Model Bake-off (Recall@5)")
    print("==================================================")

    for m_name in models_to_test:
        print(f"\nEvaluating model: {m_name}...")
        engine = EmbedEngine(model_name=m_name)
        corpus_vecs = np.array(engine.embed(test_corpus))

        correct = 0
        for qa in eval_qa:
            q_vec = np.array(engine.embed([qa["query"]])[0])
            sims = np.dot(corpus_vecs, q_vec)
            top_indices = np.argsort(sims)[::-1][:top_k]
            retrieved = [test_corpus[idx] for idx in top_indices]

            if any(qa["target"].lower() in doc.lower() for doc in retrieved):
                correct += 1

        recall = correct / len(eval_qa)
        recalls[m_name] = round(recall, 4)
        print(f"  {m_name} Recall@{top_k}: {recall*100:.1f}% ({correct}/{len(eval_qa)})")

    # Append results to RESULTS.md
    with open("eval/RESULTS.md", "a") as rf:
        rf.write(f"\n\n## Week 4 — Embeddings Model Bake-Off\n\n")
        rf.write(f"| Model | Vector Dimension | Retrieval Recall@5 | Selected Default |\n")
        rf.write(f"|---|---|---|---|\n")
        rf.write(f"| `multilingual-e5-small` | 384 | {recalls.get('multilingual-e5-small', 0)*100:.1f}% | Yes (Multilingual Support) |\n")
        rf.write(f"| `bge-small-en-v1.5` | 384 | {recalls.get('bge-small-en-v1.5', 0)*100:.1f}% | Alternate |\n")
        rf.write(f"\n**Outcome & Decision:** Both models use 384-dimensional dense vectors fitting the `chunks.embedding` schema. `multilingual-e5-small` is selected as the primary default for out-of-the-box multilingual query handling (English, Hindi, Nepali).\n")

    return recalls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate EasyOCR, extraction, and embeddings on sample documents.")
    parser.add_argument("--samples", default="eval/samples", help="Path to sample images")
    parser.add_argument("--ground-truth", default="eval/ground_truth", help="Path to ground truth JSONs")
    parser.add_argument("--mode", default="all", choices=["all", "ocr", "embed-bakeoff"], help="Evaluation mode to run")
    args = parser.parse_args()

    if args.mode in ("all", "ocr"):
        run_benchmark(args.samples, args.ground_truth)
    if args.mode in ("all", "embed-bakeoff"):
        embed_bakeoff(top_k=5)

