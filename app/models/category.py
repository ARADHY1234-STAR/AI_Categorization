from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel


class CategoryEnum(str, Enum):
    COMMUNICATION = "Communication"
    SOCIAL_MEDIA = "Social Media"
    PRODUCTIVITY_OFFICE = "Productivity & Office"
    DEVELOPMENT_IT = "Development & IT"
    BUSINESS_ENTERPRISE = "Business & Enterprise"
    RESEARCH_LEARNING = "Research & Learning"
    ENTERTAINMENT_MEDIA = "Entertainment & Media"
    SHOPPING_ECOMMERCE = "Shopping & E-commerce"
    SYSTEM_UTILITIES_SECURITY = "System Utilities & Security"
    FILE_STORAGE_DATA_SHARING = "File Storage & Data Sharing"
    MISCELLANEOUS = "Miscellaneous"


class CategoryMeta(BaseModel):
    id: int
    name: CategoryEnum
    description: str
    examples_scope: str


CATEGORIES_REGISTRY: Dict[int, CategoryMeta] = {
    1: CategoryMeta(
        id=1,
        name=CategoryEnum.COMMUNICATION,
        description="Messaging, email, voice/video calls, team collaboration",
        examples_scope="Slack, Teams, Zoom, Gmail, Discord, Telegram, WhatsApp",
    ),
    2: CategoryMeta(
        id=2,
        name=CategoryEnum.SOCIAL_MEDIA,
        description="Social networking, content sharing, live streaming, short-form video, professional networking, discussion platforms",
        examples_scope="Instagram, Reddit, X/Twitter, LinkedIn, Facebook",
    ),
    3: CategoryMeta(
        id=3,
        name=CategoryEnum.PRODUCTIVITY_OFFICE,
        description="Document/spreadsheet/presentation editors, notes, calendars, task/project/planning tools",
        examples_scope="Google Docs, Notion, Airtable, Microsoft Word Online, Trello, Asana, Jira, Monday.com, Todoist, Google Calendar",
    ),
    4: CategoryMeta(
        id=4,
        name=CategoryEnum.DEVELOPMENT_IT,
        description="Coding, version control, DevOps, API testing, database management, cloud infrastructure, containerization, sysadmin",
        examples_scope="GitHub, GitLab, Postman, Docker, Kubernetes, CI/CD tools",
    ),
    5: CategoryMeta(
        id=5,
        name=CategoryEnum.BUSINESS_ENTERPRISE,
        description="CRM, ERP, HRMS, payroll, accounting, procurement, customer support/ticketing, workflow automation",
        examples_scope="Salesforce, Workday, SAP, NetSuite, Zendesk, QuickBooks, ServiceNow",
    ),
    6: CategoryMeta(
        id=6,
        name=CategoryEnum.RESEARCH_LEARNING,
        description="Search/reference, courses, technical documentation, knowledge bases, digital libraries",
        examples_scope="Wikipedia, Coursera, edX, JSTOR, Khan Academy, Duolingo",
    ),
    7: CategoryMeta(
        id=7,
        name=CategoryEnum.ENTERTAINMENT_MEDIA,
        description="Video, music, games, podcasts, news, live broadcasts consumed as produced media",
        examples_scope="YouTube, Twitch, TikTok, Netflix, Spotify, Steam, BBC, CNN",
    ),
    8: CategoryMeta(
        id=8,
        name=CategoryEnum.SHOPPING_ECOMMERCE,
        description="Purchasing, marketplaces, food delivery, travel booking, digital subscriptions, payments",
        examples_scope="Amazon, eBay, DoorDash, UberEats, Booking.com, Airbnb, Shopify",
    ),
    9: CategoryMeta(
        id=9,
        name=CategoryEnum.SYSTEM_UTILITIES_SECURITY,
        description="System maintenance, file management/backup, remote access, VPN, antivirus, compression, device management",
        examples_scope="Antivirus, personal VPN, disk utilities, device management utilities",
    ),
    10: CategoryMeta(
        id=10,
        name=CategoryEnum.FILE_STORAGE_DATA_SHARING,
        description="Cloud storage, sync, document repositories, file transfer, shared drives, backup",
        examples_scope="Google Drive, OneDrive, Dropbox, WeTransfer, Box, SharePoint document libraries",
    ),
    11: CategoryMeta(
        id=11,
        name=CategoryEnum.MISCELLANEOUS,
        description="Websites/domains that cannot be confidently classified into Categories 1–10 based on the available metadata and classification rules.",
        examples_scope="Unclassifiable, low confidence, ambiguous, or sparse websites lacking sufficient classification evidence",
    ),
}

# Lookup dictionaries
CATEGORY_NAME_TO_ID: Dict[str, int] = {
    meta.name.value: cat_id for cat_id, meta in CATEGORIES_REGISTRY.items()
}

CATEGORY_ID_TO_NAME: Dict[int, str] = {
    cat_id: meta.name.value for cat_id, meta in CATEGORIES_REGISTRY.items()
}

ALLOWED_CATEGORY_NAMES: List[str] = [cat.value for cat in CategoryEnum]

MISCELLANEOUS_CATEGORY_ID: int = 11
MISCELLANEOUS_CATEGORY_NAME: str = CategoryEnum.MISCELLANEOUS.value


def get_category_id_by_name(name: str) -> Optional[int]:
    """Retrieve category ID by canonical category name."""
    return CATEGORY_NAME_TO_ID.get(name)


def get_category_name_by_id(cat_id: int) -> Optional[str]:
    """Retrieve canonical category name by ID."""
    return CATEGORY_ID_TO_NAME.get(cat_id)
