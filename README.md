# Website/Domain Categorization AI System

A standalone, production-grade backend AI service that categorizes website domains and subdomains into exactly one of 10 predefined categories using a strict **Two-Layer Architecture**:
1. **Layer 1: HTTP Metadata Fetcher** (SSRF-protected, follows redirects, extracts title/meta/OG/headings/schema.org, per-host rate limiting).
2. **Layer 2: LLM Categorizer** (OpenRouter / Gemini 3.7 Flash, locked rules F1 & TB1–TB8 injection, strict JSON output validation).

---

## Target Architecture

Every URL goes through HTTP metadata extraction first, followed by LLM categorization second, with NO preliminary domain-only LLM pre-guessing:

```text
       URL
        │
        ▼
   URL Normalizer (Configurable Meaningful Subdomains & Post-Redirect)
        │
        ▼
   LAYER 1: HTTP Metadata Fetcher (SSRF protection, redirect tracking, per-host politeness)
        │
        ▼
   Structured Metadata (Title, Desc, OG tags, Headings, Schema.org, Body snippet)
        │
        ▼
   LAYER 2: LLM Categorizer (OpenRouter Gemini 3.7 Flash)
        │
        ▼
   Rule & Judgment Validation (F1, TB1–TB8)
        │
        ▼
   One of 10 Categories
        │
        ▼
   Database (SQLite / PostgreSQL with Human-Override Protection)
```

---

## The 10 Fixed Categories

| ID | Category | Description | Scope / Examples |
|---|---|---|---|
| **1** | **Communication** | Messaging, email, voice/video calls, team collaboration | Slack, Teams, Zoom, Gmail, Discord, Telegram, WhatsApp |
| **2** | **Social Media** | Social networking, content sharing, live streaming, discussion platforms | Instagram, Reddit, X/Twitter, LinkedIn, Facebook |
| **3** | **Productivity & Office** | Document/spreadsheet/presentation editors, notes, calendars, task/project tools | Google Docs, Notion, Airtable, Microsoft Word Online, Trello, Asana, Jira |
| **4** | **Development & IT** | Coding, version control, DevOps, API testing, database management, cloud infra | GitHub, GitLab, Postman, Docker, Kubernetes |
| **5** | **Business & Enterprise** | CRM, ERP, HRMS, payroll, accounting, procurement, customer support/ticketing | Salesforce, Workday, SAP, NetSuite, Zendesk, QuickBooks |
| **6** | **Research & Learning** | Search/reference, courses, technical documentation, knowledge bases | Wikipedia, Coursera, edX, JSTOR, Khan Academy |
| **7** | **Entertainment & Media** | Video, music, games, podcasts, news, produced media | YouTube, Twitch, TikTok, Netflix, Spotify, Steam |
| **8** | **Shopping & E-commerce** | Purchasing, marketplaces, food delivery, travel booking, payments | Amazon, eBay, DoorDash, UberEats, Booking.com, Airbnb |
| **9** | **System Utilities & Security** | System maintenance, file management/backup, remote access, VPN, antivirus | Antivirus, personal VPN, disk utilities |
| **10** | **File Storage & Data Sharing** | Cloud storage, sync, document repositories, file transfer, shared drives | Google Drive, OneDrive, Dropbox, WeTransfer, Box |

---

## Locked Business Rules (F1, TB1–TB8)

- **F1 (Classification Unit)**: Root domain gets its default category; meaningful subdomains are classified independently.
- **TB1 (Communication vs Social Media)**: Secondary DMs on public network $\rightarrow$ Social Media; core private/group messaging $\rightarrow$ Communication.
- **TB2 (Social Media vs Entertainment & Media)**: Produced media core $\rightarrow$ Entertainment & Media (YouTube, Twitch, TikTok); social profile/feed $\rightarrow$ Social Media (Instagram).
- **TB3 (Communication vs Business & Enterprise)**: Messaging/calls $\rightarrow$ Communication regardless of B2B/B2C (Slack, Teams, Zoom). Business & Enterprise is strictly CRM/ERP/HRMS/Finance.
- **TB4 (Classification Granularity)**: Categorization is at domain/subdomain level. URL paths and subreddits are ignored.
- **TB5 (Productivity & Office vs Business & Enterprise)**: Doc/sheet/note editors $\rightarrow$ Productivity & Office (Notion, Airtable, Google Docs). Business & Enterprise is dedicated CRM/ERP/HRMS/Ticketing (Salesforce).
- **TB6 (Subdomain-Level Function Split)**: Multi-service subdomains classified by primary function (`drive.google.com` $\rightarrow$ File Storage; `docs.google.com` $\rightarrow$ Productivity & Office).
- **TB7 (Task, Calendar & Project Tools)**: General task/calendar/project/planning tools $\rightarrow$ Productivity & Office (Trello, Asana, Monday.com, Jira, Google Calendar).
- **TB8 (Cloud Storage Uniformity)**: Cloud storage/sync/file-transfer services $\rightarrow$ File Storage & Data Sharing uniformly (WeTransfer, Dropbox, Google Drive, OneDrive).

---

## Project Structure

```
d:/AI_Categorization/
├── .env.example                       # Environment variables template
├── .gitignore                         # Git ignore rules
├── requirements.txt                   # Dependencies
├── pytest.ini                         # Pytest config
├── README.md                          # Documentation
│
├── app/
│   ├── api/
│   │   └── server.py                  # FastAPI REST API & dashboard
│   ├── classifier/
│   │   ├── client.py                  # OpenRouter LLM client
│   │   ├── pipeline.py                # Two-Layer classification pipeline
│   │   ├── prompts.py                 # Layer 2 prompt builder with sparse HTML handling
│   │   └── bulk.py                    # 100k Bulk deduplication & batch processor
│   ├── config/
│   │   └── settings.py                # Pydantic Settings
│   ├── database/
│   │   ├── connection.py              # SQLAlchemy engine & session factory
│   │   ├── models.py                  # DB schema with post-redirect & status columns
│   │   └── repository.py              # CRUD with human-override protection & auto-migration
│   ├── enrichment/
│   │   ├── fetcher.py                 # Layer 1 HTTPMetadataFetcher with redirect tracing
│   │   ├── parser.py                  # HTML metadata parser (OG, schema.org, headings)
│   │   └── ssrf.py                    # SSRF IP & DNS security validation
│   ├── models/
│   │   ├── category.py                # 10 Fixed categories enum & registry
│   │   └── schemas.py                 # Pydantic models (FetchResult, LLMOutput, etc.)
│   ├── normalization/
│   │   └── normalizer.py              # Normalization with configurable subdomains
│   └── rules/
│       ├── base.py                    # Rule dataclass, registry & prompt generator
│       ├── locked_rules.py            # F1, TB1–TB8 implementations
│       └── overrides.py               # Fast brand overrides engine
│
├── data/
│   ├── brand_overrides.json           # Brand overrides (F1)
│   ├── meaningful_subdomains.json     # Configurable meaningful subdomains (TB6)
│   ├── evaluation_category_mapping.json # Configurable test dataset mapping table
│   ├── sample_domains.csv             # Sample batch URLs
│   └── website_category_test_dataset_100.csv # 100-domain evaluation dataset
│
├── scripts/
│   ├── classify_domain.py             # Real-time CLI classification tool
│   ├── bulk_classify.py               # High-throughput batch processor
│   ├── seed_database.py               # Default dataset seeder (40 canonical domains)
│   └── evaluate_dataset.py            # Evaluation benchmark against test dataset
│
└── tests/
    ├── conftest.py                    # Pytest fixtures
    ├── test_classifier_pipeline.py    # Two-layer flow & sparse metadata tests
    ├── test_database.py               # DB CRUD & human-override immunity tests
    ├── test_evaluation_mapping.py     # Evaluation mapping table tests
    ├── test_normalization.py          # Normalization & subdomain tests
    ├── test_overrides.py              # Brand override tests
    ├── test_rules.py                  # Locked business rules tests
    ├── test_ssrf_and_enrichment.py    # SSRF & HTML parser tests
    └── test_bulk_deduplication.py     # 5,000 duplicate deduplication test
```

---

## Setup & Execution

### 1. Environment Setup
```bash
# Activate virtual environment
.\.venv\Scripts\activate.bat   # (or .\.venv\Scripts\Activate.ps1 on PowerShell)

# Install requirements
pip install -r requirements.txt
```

Configure `.env`:
```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=google/gemini-3.7-flash
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
CLASSIFIER_CONFIDENCE_THRESHOLD=0.80
DATABASE_URL=sqlite:///data/domains.db
```

---

### 2. How to Run the Application

#### A. Interactive Web Dashboard & REST API
```bash
uvicorn app.api.server:app --reload --port 8000
```
- Open Web Dashboard: **[http://localhost:8000](http://localhost:8000)**
- Interactive Swagger API: **[http://localhost:8000/docs](http://localhost:8000/docs)**

#### B. Classify a Single URL (CLI)
```bash
python scripts/classify_domain.py https://karyakeeper.com
python scripts/classify_domain.py https://docs.google.com/document/d/123
python scripts/classify_domain.py --demo-sequence
```

#### C. High-Throughput Bulk Batch Processing
```bash
python scripts/bulk_classify.py data/sample_domains.csv --output results.csv
```

#### D. Run Evaluation Benchmark on Test Dataset
```bash
python scripts/evaluate_dataset.py data/website_category_test_dataset_100.csv --output data/evaluation_results.csv
```
- **Configurable Mapping Table**: Categories in test datasets are translated into our 10 canonical categories via `data/evaluation_category_mapping.json`.
- **Hard Security Constraint**: `Expected_Category` is **NEVER** sent to the LLM; it is strictly used post-classification for scoring.

#### E. Run Automated Test Suite
```bash
python -m pytest -v
```
