import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.settings import get_settings
from app.database.connection import init_db, get_db_session
from app.classifier.pipeline import DomainClassificationPipeline

# Configure logging to display clean info messages
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)


async def main():
    parser = argparse.ArgumentParser(
        description="Real-time Website/Domain Categorization CLI"
    )
    parser.add_argument(
        "domain",
        nargs="?",
        default=None,
        help="Domain or URL to classify (e.g. youtube.com, docs.google.com)",
    )
    parser.add_argument(
        "--subdomain",
        default=None,
        help="Explicit subdomain if passed separately",
    )
    parser.add_argument(
        "--app-name",
        default=None,
        help="Optional application or website name",
    )
    parser.add_argument(
        "--demo-sequence",
        action="store_true",
        help="Run the required 3-step demonstration sequence",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass database cache and force fresh classification",
    )

    args = parser.parse_args()

    # Initialize DB schema
    init_db()
    pipeline = DomainClassificationPipeline()

    if args.demo_sequence:
        print("\n=======================================================")
        print("  REAL-TIME CLASSIFICATION DEMONSTRATION SEQUENCE")
        print("=======================================================\n")

        # Step 1: Known domain (First request -> Brand Override / LLM -> DB Store)
        domain_1 = "youtube.com"
        print(f"--- STEP 1: First request for known domain: '{domain_1}' ---")
        res1 = await pipeline.classify(domain_1)
        print(json.dumps(res1.model_dump(), indent=2))

        # Step 2: Same domain again (Second request -> DB Hit, zero AI call)
        print(f"\n--- STEP 2: Second request for same domain: '{domain_1}' ---")
        res2 = await pipeline.classify(domain_1)
        print(json.dumps(res2.model_dump(), indent=2))
        assert res2.source == "database", "Step 2 should hit database cache!"

        # Step 3: Domain that triggers HTTP enrichment flow
        domain_3 = "example.com"
        print(f"\n--- STEP 3: Domain triggering HTTP Enrichment flow: '{domain_3}' ---")
        res3 = await pipeline.classify(domain_3, force_refresh=True)
        print(json.dumps(res3.model_dump(), indent=2))
        print("\nDemo sequence completed successfully!\n")
        return

    if not args.domain:
        parser.print_help()
        sys.exit(1)

    print(f"\nClassifying domain: '{args.domain}'...")
    result = await pipeline.classify(
        raw_input=args.domain,
        subdomain=args.subdomain,
        app_name=args.app_name,
        force_refresh=args.force_refresh,
    )
    print("\nResult:")
    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
