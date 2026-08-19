import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import init_db
from app.classifier.bulk import BulkClassifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


async def main():
    parser = argparse.ArgumentParser(
        description="High-Throughput Bulk Website/Domain Categorization"
    )
    parser.add_argument(
        "input_csv",
        nargs="?",
        default="data/sample_domains.csv",
        help="Path to input CSV file (default: data/sample_domains.csv)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="results.csv",
        help="Path to output CSV results file (default: results.csv)",
    )

    args = parser.parse_args()

    # Ensure DB schema is ready
    init_db()

    classifier = BulkClassifier()
    print(f"\nProcessing bulk CSV: '{args.input_csv}'...")
    results, summary = await classifier.process_csv(
        input_csv_path=args.input_csv,
        output_csv_path=args.output,
    )

    print("\n=======================================================")
    print("                BULK PROCESSING SUMMARY                ")
    print("=======================================================")
    print(f"Total Input Rows Processed:   {summary.total_input_rows}")
    print(f"Unique Domains Deduplicated:  {summary.unique_domains_count}")
    print(f"Database Cache Hits:          {summary.cached_hits_count}")
    print(f"Brand Override Hits:          {summary.brand_override_count}")
    print(f"Domain-Only LLM Decisions:    {summary.llm_domain_only_count}")
    print(f"Enriched LLM Decisions:       {summary.llm_enriched_count}")
    print(f"Unknown / Errors:             {summary.unknown_or_error_count}")
    print(f"Total Processing Time:        {summary.processing_time_seconds:.2f}s")
    print(f"Output saved to:              {args.output}")
    print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(main())
