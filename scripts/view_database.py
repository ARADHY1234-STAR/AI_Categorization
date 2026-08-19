import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import init_db, get_db_session
from app.database.models import DomainClassificationModel


def view_domains(limit: int = 50, search: str = ""):
    """Print formatted table of classified domains in the database."""
    init_db()
    db = get_db_session()
    try:
        query = db.query(DomainClassificationModel)
        if search:
            query = query.filter(
                (DomainClassificationModel.fqdn.ilike(f"%{search}%")) |
                (DomainClassificationModel.category_name.ilike(f"%{search}%"))
            )
        records = query.order_by(DomainClassificationModel.id.asc()).limit(limit).all()

        if not records:
            print("\nNo classification records found in database.")
            return

        print("\n" + "=" * 115)
        print(f" {'ID':<4} | {'FQDN (Domain/Subdomain)':<32} | {'Category':<28} | {'Conf':<6} | {'Source':<18} | {'Status':<10}")
        print("=" * 115)

        for r in records:
            cat = r.category_name or "UNKNOWN"
            src = r.classification_source or "—"
            stat = r.status or "—"
            conf = f"{r.confidence:.2f}"
            print(f" {r.id:<4} | {r.fqdn:<32} | {cat:<28} | {conf:<6} | {src:<18} | {stat:<10}")

        print("=" * 115)
        print(f"Showing {len(records)} records (Database: data/domains.db)\n")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View classified domains in SQLite database")
    parser.add_argument("--limit", "-n", type=int, default=50, help="Max records to display (default: 50)")
    parser.add_argument("--search", "-s", type=str, default="", help="Filter by domain or category name")
    args = parser.parse_args()

    view_domains(limit=args.limit, search=args.search)
