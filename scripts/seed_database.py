import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.connection import init_db, get_db_session
from app.database.repository import DomainRepository
from app.models.schemas import ClassificationSource
from app.normalization.normalizer import normalize_domain

DEFAULT_SEED_DOMAINS = [
    # 1. Communication
    {"domain": "discord.com", "category": "Communication", "source": "brand_override", "reason": "Core product is private/group messaging (TB1, F1)"},
    {"domain": "telegram.org", "category": "Communication", "source": "brand_override", "reason": "Core product is messaging (TB1, F1)"},
    {"domain": "whatsapp.com", "category": "Communication", "source": "brand_override", "reason": "Core product is messaging (TB1, F1)"},
    {"domain": "slack.com", "category": "Communication", "source": "human_override", "reason": "Team collaboration & messaging platform (TB3)"},
    {"domain": "zoom.us", "category": "Communication", "source": "human_override", "reason": "Video conferencing & messaging (TB3)"},
    {"domain": "mail.google.com", "subdomain": "mail", "category": "Communication", "source": "human_override", "reason": "Email service subdomain (TB6)"},
    
    # 2. Social Media
    {"domain": "instagram.com", "category": "Social Media", "source": "human_override", "reason": "Social profile & photo sharing network (TB2)"},
    {"domain": "reddit.com", "category": "Social Media", "source": "human_override", "reason": "Discussion forum & social content platform (TB4)"},
    {"domain": "linkedin.com", "category": "Social Media", "source": "human_override", "reason": "Professional networking & social platform"},
    {"domain": "x.com", "category": "Social Media", "source": "human_override", "reason": "Public social feed & microblogging (TB1)"},

    # 3. Productivity & Office
    {"domain": "docs.google.com", "subdomain": "docs", "category": "Productivity & Office", "source": "human_override", "reason": "Document editing application (TB5, TB6)"},
    {"domain": "sheets.google.com", "subdomain": "sheets", "category": "Productivity & Office", "source": "human_override", "reason": "Spreadsheet application (TB5, TB6)"},
    {"domain": "notion.so", "category": "Productivity & Office", "source": "human_override", "reason": "Notes, docs, and knowledge workspace (TB5)"},
    {"domain": "airtable.com", "category": "Productivity & Office", "source": "human_override", "reason": "Spreadsheet-database workspace (TB5)"},
    {"domain": "trello.com", "category": "Productivity & Office", "source": "human_override", "reason": "Project & task planning board (TB7)"},
    {"domain": "asana.com", "category": "Productivity & Office", "source": "human_override", "reason": "Project & task management tool (TB7)"},

    # 4. Development & IT
    {"domain": "github.com", "category": "Development & IT", "source": "human_override", "reason": "Source code hosting & version control"},
    {"domain": "gitlab.com", "category": "Development & IT", "source": "human_override", "reason": "DevOps & code repository platform"},
    {"domain": "postman.com", "category": "Development & IT", "source": "human_override", "reason": "API development and testing platform"},
    {"domain": "docker.com", "category": "Development & IT", "source": "human_override", "reason": "Containerization platform & registry"},

    # 5. Business & Enterprise
    {"domain": "salesforce.com", "category": "Business & Enterprise", "source": "human_override", "reason": "Enterprise CRM platform (TB3, TB5)"},
    {"domain": "workday.com", "category": "Business & Enterprise", "source": "human_override", "reason": "Enterprise HRMS & financial management (TB5)"},
    {"domain": "zendesk.com", "category": "Business & Enterprise", "source": "human_override", "reason": "Customer support & ticketing system (TB5)"},
    {"domain": "sap.com", "category": "Business & Enterprise", "source": "human_override", "reason": "Enterprise ERP & business process system (TB5)"},

    # 6. Research & Learning
    {"domain": "wikipedia.org", "category": "Research & Learning", "source": "human_override", "reason": "Free digital encyclopedia and reference library"},
    {"domain": "coursera.org", "category": "Research & Learning", "source": "human_override", "reason": "Online course platform & education"},
    {"domain": "khanacademy.org", "category": "Research & Learning", "source": "human_override", "reason": "Educational learning resource"},

    # 7. Entertainment & Media
    {"domain": "youtube.com", "category": "Entertainment & Media", "source": "brand_override", "reason": "Produced video & multimedia consumption (TB2, F1)"},
    {"domain": "twitch.tv", "category": "Entertainment & Media", "source": "human_override", "reason": "Live streaming video platform (TB2)"},
    {"domain": "netflix.com", "category": "Entertainment & Media", "source": "human_override", "reason": "Subscription streaming entertainment"},
    {"domain": "spotify.com", "category": "Entertainment & Media", "source": "human_override", "reason": "Audio & music streaming platform"},

    # 8. Shopping & E-commerce
    {"domain": "amazon.com", "category": "Shopping & E-commerce", "source": "human_override", "reason": "Online retail marketplace & consumer purchasing"},
    {"domain": "ebay.com", "category": "Shopping & E-commerce", "source": "human_override", "reason": "Online marketplace & auction platform"},
    {"domain": "shopify.com", "category": "Shopping & E-commerce", "source": "human_override", "reason": "E-commerce platform and merchant tools"},

    # 9. System Utilities & Security
    {"domain": "speedtest.net", "category": "System Utilities & Security", "source": "human_override", "reason": "Network diagnostics & speed testing utility"},
    {"domain": "malwarebytes.com", "category": "System Utilities & Security", "source": "human_override", "reason": "Antivirus & system security utility"},

    # 10. File Storage & Data Sharing
    {"domain": "drive.google.com", "subdomain": "drive", "category": "File Storage & Data Sharing", "source": "human_override", "reason": "Cloud storage & file sync repository (TB6, TB8)"},
    {"domain": "onedrive.live.com", "subdomain": "onedrive", "category": "File Storage & Data Sharing", "source": "human_override", "reason": "Cloud storage & file backup (TB6, TB8)"},
    {"domain": "dropbox.com", "category": "File Storage & Data Sharing", "source": "human_override", "reason": "Cloud file storage & syncing (TB8)"},
    {"domain": "wetransfer.com", "category": "File Storage & Data Sharing", "source": "human_override", "reason": "File transfer and sharing service (TB8)"},
]


def seed_database(verbose: bool = True) -> int:
    """Insert default verified domain dataset into the classification database."""
    init_db()
    db = get_db_session()
    inserted_count = 0
    try:
        repo = DomainRepository(db)
        for item in DEFAULT_SEED_DOMAINS:
            norm = normalize_domain(
                raw_input=item["domain"],
                explicit_subdomain=item.get("subdomain"),
            )
            src_str = item.get("source", "human_override")
            src_enum = (
                ClassificationSource.BRAND_OVERRIDE
                if src_str == "brand_override"
                else ClassificationSource.HUMAN_OVERRIDE
            )
            is_human = (src_enum == ClassificationSource.HUMAN_OVERRIDE)

            repo.save_classification(
                norm=norm,
                category=item["category"],
                confidence=1.0,
                source=src_enum,
                status="CLASSIFIED" if not is_human else "OVERRIDE",
                is_human_override=is_human,
                original_url=item["domain"],
                final_url=item["domain"],
                metadata_fetch_status="SEEDED",
                rule_version="Seed Dataset / Locked Rules",
                reason=item.get("reason"),
            )
            inserted_count += 1
            if verbose:
                print(f"  [+] Seeded: {norm.fqdn:<25} -> {item['category']} ({item['source']})")


        if verbose:
            print(f"\nSuccessfully seeded {inserted_count} verified domain classifications!")

        return inserted_count
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed classification database with default verified domains")
    parser.parse_args()
    print("\nSeeding default verified dataset into database...")
    seed_database(verbose=True)
