import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import init_db
from app.classifier.pipeline import DomainClassificationPipeline
from app.models.category import ALLOWED_CATEGORY_NAMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_category_mapping(mapping_file: str = "data/evaluation_category_mapping.json") -> Dict[str, str]:
    """Load configurable dataset category -> canonical 10 categories mapping table."""
    path = Path(mapping_file)
    if not path.exists():
        logger.warning(f"Category mapping file not found at {mapping_file}. Using 1:1 identity.")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("mappings", {})
    except Exception as e:
        logger.error(f"Failed to load category mappings from {mapping_file}: {e}")
        return {}


async def evaluate_csv(
    csv_path: str,
    mapping_path: str = "data/evaluation_category_mapping.json",
    output_report_csv: Optional[str] = "data/evaluation_results.csv",
    force_refresh: bool = False,
):
    """Run full evaluation pipeline against test dataset with configurable category mapping."""
    init_db()
    pipeline = DomainClassificationPipeline()
    category_mapping = load_category_mapping(mapping_path)

    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Evaluation dataset CSV not found at: {csv_path}")

    # Read rows
    rows: List[Dict[str, str]] = []
    with open(path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            clean = {k.strip(): v.strip() if v else "" for k, v in r.items() if k}
            rows.append(clean)

    total_rows = len(rows)
    print(f"\n=======================================================")
    print(f"      STARTING EVALUATION BENCHMARK ({total_rows} ROWS)      ")
    print(f"=======================================================\n")

    matches = 0
    mismatches = 0
    unmapped_cases = 0
    evaluation_records = []

    for idx, row in enumerate(rows):
        raw_url = row.get("URL") or row.get("url") or row.get("Website") or row.get("website") or ""
        website_name = row.get("Website") or row.get("website") or row.get("Name") or None
        raw_expected = row.get("Expected_Category") or row.get("expected_category") or row.get("Category") or ""

        if not raw_url:
            continue

        # CRITICAL HARD CONSTRAINT: Expected_Category is NEVER passed to the classifier
        try:
            classification = await pipeline.classify(
                raw_input=raw_url,
                app_name=website_name,
                force_refresh=force_refresh,
            )
        except Exception as e:
            logger.error(f"Error classifying {raw_url}: {e}")
            classification = None

        ai_category = classification.category if classification else None

        # Map dataset category string to canonical 11 categories
        mapped_expected = category_mapping.get(raw_expected, raw_expected)
        is_mapped = raw_expected in category_mapping or mapped_expected in ALLOWED_CATEGORY_NAMES

        if not is_mapped:
            unmapped_cases += 1
            eval_status = "UNMAPPED_DATASET_CATEGORY"
        elif ai_category == mapped_expected:
            matches += 1
            eval_status = "MATCH"
        else:
            mismatches += 1
            eval_status = "MISMATCH"

        record = {
            "index": idx + 1,
            "website": website_name or "",
            "url": raw_url,
            "domain": classification.domain if classification else "",
            "raw_expected": raw_expected,
            "mapped_expected": mapped_expected,
            "ai_assigned_category": ai_category or "UNKNOWN",
            "confidence": f"{classification.confidence:.2f}" if classification else "0.00",
            "source": classification.source if classification else "error",
            "eval_status": eval_status,
            "rule_applied": classification.rule_applied if classification else "",
            "reason": classification.reason if classification else "",
        }
        evaluation_records.append(record)

        icon = "[MATCH]" if eval_status == "MATCH" else ("[UNMAPPED]" if eval_status == "UNMAPPED_DATASET_CATEGORY" else "[MISMATCH]")
        print(f"[{idx+1}/{total_rows}] {icon:<10} {raw_url:<35} -> AI: '{ai_category}' | Expected: '{mapped_expected}'")


    # Accuracy calculations
    mappable_total = matches + mismatches
    accuracy_pct = (matches / mappable_total * 100.0) if mappable_total > 0 else 0.0

    print("\n=======================================================")
    print("                EVALUATION SUMMARY REPORT               ")
    print("=======================================================")
    print(f"Total Rows Evaluated:         {len(evaluation_records)}")
    print(f"Exact Matches:                {matches}")
    print(f"Mismatches:                   {mismatches}")
    print(f"Unmapped / Unclear Categories: {unmapped_cases}")
    print(f"Benchmark Accuracy (Mappable): {accuracy_pct:.1f}%")
    print("=======================================================\n")

    # Write output report CSV
    if output_report_csv:
        out_p = Path(output_report_csv)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "index", "website", "url", "domain", "raw_expected",
                    "mapped_expected", "ai_assigned_category", "confidence",
                    "source", "eval_status", "rule_applied", "reason"
                ]
            )
            writer.writeheader()
            writer.writerows(evaluation_records)
        print(f"Detailed evaluation report saved to: {output_report_csv}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate Classification Pipeline against Test Dataset")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="data/website_category_test_dataset_100.csv",
        help="Path to evaluation test CSV (default: data/website_category_test_dataset_100.csv)",
    )
    parser.add_argument(
        "--mapping",
        "-m",
        default="data/evaluation_category_mapping.json",
        help="Path to category mapping JSON (default: data/evaluation_category_mapping.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/evaluation_results.csv",
        help="Path to output evaluation report CSV (default: data/evaluation_results.csv)",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass database cache to force fresh Layer 1 fetch and Layer 2 classification",
    )

    args = parser.parse_args()
    asyncio.run(evaluate_csv(
        csv_path=args.csv_path,
        mapping_path=args.mapping,
        output_report_csv=args.output,
        force_refresh=args.force_refresh,
    ))
