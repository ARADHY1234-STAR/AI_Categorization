from app.models.category import CategoryEnum
from app.rules.base import Rule, RuleRegistry, RuleScope, rule_registry


def register_locked_rules(registry: RuleRegistry = rule_registry) -> None:
    """Register locked business rules F1, TB1–TB8."""

    registry.register(
        Rule(
            rule_id="F1",
            name="Classification Unit & Subdomain Independence",
            description="Root domain gets its own default category; meaningful subdomains are classified independently of their root domain.",
            scope=RuleScope.GLOBAL,
            precedence=100,
            prompt_instruction="Evaluate the specific subdomain when present. Subdomains have independent functional classifications from their root domain.",
        )
    )

    registry.register(
        Rule(
            rule_id="TB1",
            name="Communication vs Social Media",
            description="Secondary DMs on a primarily public platform -> Social Media. Core-product private/group messaging -> Communication.",
            scope=RuleScope.DISAMBIGUATION,
            precedence=90,
            category_affinity=[CategoryEnum.COMMUNICATION, CategoryEnum.SOCIAL_MEDIA],
            prompt_instruction="If the core product is private/group messaging or calling (Discord, Telegram, WhatsApp, Messenger, Zoom), classify as 'Communication'. If DMs are secondary features on a primarily public social profile/feed/network platform (X/Twitter, Reddit, Instagram, Facebook), classify as 'Social Media'.",
        )
    )

    registry.register(
        Rule(
            rule_id="TB2",
            name="Social Media vs Entertainment & Media",
            description="Produced media (video/stream) as core content unit -> Entertainment & Media. Social profile/post/status as core content unit -> Social Media.",
            scope=RuleScope.DISAMBIGUATION,
            precedence=90,
            category_affinity=[CategoryEnum.SOCIAL_MEDIA, CategoryEnum.ENTERTAINMENT_MEDIA],
            prompt_instruction="If produced media (video, live stream, audio, broadcast) is the primary consumed content unit (e.g. YouTube, Twitch, TikTok, Netflix, Spotify), classify as 'Entertainment & Media'. If personal profiles, status updates, discussion feeds, or social graphs are the primary unit (e.g. Instagram, Reddit, Threads, LinkedIn, Facebook), classify as 'Social Media'.",
        )
    )

    registry.register(
        Rule(
            rule_id="TB3",
            name="Communication vs Business & Enterprise",
            description="Communication applies regardless of B2C/B2B context (Slack, Teams, Zoom -> Communication). Business & Enterprise is strictly CRM/ERP/HRMS/Finance/Payroll.",
            scope=RuleScope.DISAMBIGUATION,
            precedence=90,
            category_affinity=[CategoryEnum.COMMUNICATION, CategoryEnum.BUSINESS_ENTERPRISE],
            prompt_instruction="Communication tools (Slack, Microsoft Teams, Zoom, Webex, Google Meet) MUST be classified as 'Communication', even in enterprise/B2B settings. 'Business & Enterprise' is reserved strictly for structured business process systems: CRM, ERP, HRMS, payroll, accounting, procurement, and customer support/ticketing.",
        )
    )

    registry.register(
        Rule(
            rule_id="TB4",
            name="Classification Granularity",
            description="Classification is always performed at domain/subdomain level. URL path, subreddit, or page content items are never used to determine category.",
            scope=RuleScope.GLOBAL,
            precedence=95,
            prompt_instruction="Classify based solely on the overall domain/subdomain platform identity. Ignore specific URL paths, subreddits, channels, or individual content items (e.g., reddit.com is uniformly 'Social Media' regardless of the topic of a subreddit).",
        )
    )

    registry.register(
        Rule(
            rule_id="TB5",
            name="Productivity & Office vs Business & Enterprise",
            description="Document/note/spreadsheet/presentation editors -> Productivity & Office. Business & Enterprise is dedicated structured business processes.",
            scope=RuleScope.DISAMBIGUATION,
            precedence=90,
            category_affinity=[CategoryEnum.PRODUCTIVITY_OFFICE, CategoryEnum.BUSINESS_ENTERPRISE],
            prompt_instruction="Document, note, spreadsheet, or presentation creation/editing tools (Notion, Airtable, Google Docs, Sheets, Microsoft Word Online, Coda) MUST be classified as 'Productivity & Office', regardless of enterprise tier or workplace usage. 'Business & Enterprise' is strictly for dedicated CRM (Salesforce), ERP (SAP), HRMS (Workday), payroll (ADP), accounting (QuickBooks), and support ticketing (Zendesk).",
        )
    )

    registry.register(
        Rule(
            rule_id="TB6",
            name="Subdomain-Level Function Split",
            description="Classify subdomains according to their primary function, not the root brand.",
            scope=RuleScope.SUBDOMAIN,
            precedence=95,
            prompt_instruction="For multi-service suites (like Google Workspace or Microsoft 365), classify subdomains by their distinct function: drive.google.com and onedrive.live.com -> 'File Storage & Data Sharing'; docs.google.com, sheets.google.com, slides.google.com -> 'Productivity & Office'; mail.google.com and outlook.live.com -> 'Communication'.",
        )
    )

    registry.register(
        Rule(
            rule_id="TB7",
            name="Task, Calendar & Project Tools",
            description="All general task/calendar/project/note/planning tools -> Productivity & Office.",
            scope=RuleScope.DISAMBIGUATION,
            precedence=90,
            category_affinity=[CategoryEnum.PRODUCTIVITY_OFFICE, CategoryEnum.BUSINESS_ENTERPRISE],
            prompt_instruction="All general task, calendar, project management, and planning tools (Trello, Asana, Monday.com, Jira, Google Calendar, Todoist, ClickUp, Basecamp) MUST be classified as 'Productivity & Office'. Do NOT classify them as 'Business & Enterprise'.",
        )
    )

    registry.register(
        Rule(
            rule_id="TB8",
            name="Cloud Storage Uniformity",
            description="All cloud storage, sync, file-transfer, and document repositories -> File Storage & Data Sharing uniformly.",
            scope=RuleScope.DISAMBIGUATION,
            precedence=90,
            category_affinity=[CategoryEnum.FILE_STORAGE_DATA_SHARING],
            prompt_instruction="All cloud storage, file synchronization, file transfer, shared drives, and document repository services (Dropbox, Google Drive, OneDrive, Box, WeTransfer, SharePoint document libraries) MUST be classified as 'File Storage & Data Sharing' uniformly, regardless of whether used for work documents or personal files.",
        )
    )


# Automatically register locked rules on import
register_locked_rules()
