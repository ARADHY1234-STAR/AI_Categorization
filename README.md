# Website/Domain Categorization AI System

A standalone, production-grade backend AI service that categorizes website domains and subdomains into 11 predefined categories using a strict **Two-Layer Architecture**:
1. **Layer 1: HTTP Metadata Fetcher** (SSRF-protected, follows redirects, extracts title/meta/OG/headings/schema.org, per-host rate limiting).
2. **Layer 2: LLM Categorizer** (OpenRouter / Gemini 3.7 Flash, locked rules F1 & TB1–TB8 injection, strict JSON output validation).
3. **Backend Confidence Validation** (Authoritative `CONFIDENCE_THRESHOLD=0.80` enforcement routing low-confidence or unclassifiable domains into Category 11: Miscellaneous).

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
   Confidence & Validation Policy (>= 0.80 accepts Cat 1-10; < 0.80 -> Cat 11 Miscellaneous)
        │
        ▼
   Category 1–10 OR Category 11: Miscellaneous
        │
        ▼
   Database (SQLite / PostgreSQL with Human-Override Protection & Audit Status)
```

---

## The 11 Predefined Categories

| ID | Category | Definition / Description | Scope / Examples |
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
| **11** | **Miscellaneous** | Websites/domains that cannot be confidently classified into Categories 1–10 based on the available metadata and classification rules | Ambiguous, low-confidence (<0.80), unclassifiable, or sparse websites lacking sufficient classification evidence |

---

## Confidence Threshold & Miscellaneous Fallback

The system features a configurable confidence threshold (default: `0.80`) configured via environment variable `CONFIDENCE_THRESHOLD=0.80`:

- **`confidence >= 0.80`** (and valid category in Categories 1–10): Accepted as selected category with `status="CLASSIFIED"`.
- **`confidence < 0.80`**: Routed to `category_id=11`, `category="Miscellaneous"` with audit status `status="LOW_CONFIDENCE"`.
- **Unclassifiable / Empty Metadata / Unresolvable Domains**: Assigned `category_id=11`, `category="Miscellaneous"` with `status="UNCLASSIFIED"`.
- **Invalid LLM Output**: Safely handled and assigned `category_id=11`, `category="Miscellaneous"`.

> [!NOTE]
> There is no separate final "Needs Review" category. Low-confidence domains are uniformly assigned Category 11 (`Miscellaneous`), while preserving rich audit fields (`confidence`, `classification_status`, `reason`, `metadata_fetch_status`) in the database.

---

## Locked Business Rules (F1, TB1–TB8)

- **F1 (Classification Unit)**: Root domain gets its default category via brand override table; meaningful subdomains are classified independently.
- **TB1 (Communication vs Social Media)**: Secondary DMs on public network $\rightarrow$ Social Media; core private/group messaging $\rightarrow$ Communication.
- **TB2 (Social Media vs Entertainment & Media)**: Produced media core $\rightarrow$ Entertainment & Media (YouTube, Twitch, TikTok); social profile/feed $\rightarrow$ Social Media (Instagram).
- **TB3 (Communication vs Business & Enterprise)**: Messaging/calls $\rightarrow$ Communication regardless of B2B/B2C (Slack, Teams, Zoom). Business & Enterprise is strictly CRM/ERP/HRMS/Finance.
- **TB4 (Classification Granularity)**: Categorization is at domain/subdomain level. URL paths and subreddits are ignored (e.g. `reddit.com` $\rightarrow$ Social Media).
- **TB5 (Productivity & Office vs Business & Enterprise)**: Doc/sheet/note editors $\rightarrow$ Productivity & Office (Notion, Airtable, Google Docs). Business & Enterprise is dedicated CRM/ERP/HRMS/Ticketing (Salesforce).
- **TB6 (Subdomain-Level Function Split)**: Multi-service subdomains classified by primary function (`drive.google.com` $\rightarrow$ File Storage; `docs.google.com` $\rightarrow$ Productivity & Office; `mail.google.com` $\rightarrow$ Communication).
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
│   │   ├── pipeline.py                # Two-Layer classification pipeline & confidence validator
│   │   ├── prompts.py                 # Layer 2 prompt builder with 11 categories
│   │   └── bulk.py                    # 100k Bulk deduplication & batch processor
│   ├── config/
│   │   └── settings.py                # Pydantic Settings (CONFIDENCE_THRESHOLD, etc.)
│   ├── database/
│   │   ├── connection.py              # SQLAlchemy engine & session factory
│   │   ├── models.py                  # DB schema with Category 11 & audit columns
│   │   └── repository.py              # CRUD with human-override protection & auto-migration
│   ├── enrichment/
│   │   ├── fetcher.py                 # Layer 1 HTTPMetadataFetcher with redirect tracing
│   │   ├── parser.py                  # HTML metadata parser (OG, schema.org, headings)
│   │   └── ssrf.py                    # SSRF IP & DNS security validation
│   ├── models/
│   │   ├── category.py                # 11 Categories enum & registry
│   │   └── schemas.py                 # Pydantic models (FetchResult, LLMOutput, etc.)
│   ├── normalization/
│   │   └── normalizer.py              # Normalization with configurable subdomains
│   └── rules/
│   │   ├── base.py                    # Rule dataclass, registry & prompt generator
│   │   ├── locked_rules.py            # F1, TB1–TB8 implementations
│   │   └── overrides.py               # Fast brand overrides engine
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
│   ├── seed_database.py               # Default dataset seeder
│   └── evaluate_dataset.py            # Evaluation benchmark against test dataset
│
└── tests/
    ├── conftest.py                    # Pytest fixtures
    ├── test_classifier_pipeline.py    # All 11 requirement tests + pipeline flow tests
    ├── test_database.py               # DB CRUD & Category 11 persistence tests
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
CONFIDENCE_THRESHOLD=0.80
DATABASE_URL=sqlite:///data/domains.db
```

---

### 2. Running the Classifier

#### A. Interactive Web Dashboard & REST API
```bash
uvicorn app.api.server:app --reload --port 8000
```
- Web Dashboard: **[http://localhost:8000](http://localhost:8000)**
- Interactive Swagger API Docs: **[http://localhost:8000/docs](http://localhost:8000/docs)**

#### B. Classify a Single URL (CLI)
```bash
python scripts/classify_domain.py https://youtube.com
python scripts/classify_domain.py https://docs.google.com/document/d/123
python scripts/classify_domain.py https://unknown-example.com
```

#### C. High-Throughput Bulk Batch Processing
```bash
python scripts/bulk_classify.py data/sample_domains.csv --output results.csv
```

#### D. Run Evaluation Benchmark on Test Dataset
```bash
python scripts/evaluate_dataset.py data/website_category_test_dataset_100.csv --output data/evaluation_results.csv
```

#### E. Run Automated Test Suite
```bash
pytest -v
```

---

## Example Inputs & Outputs

### High-Confidence Result (Category 1–10)
```json
{
  "domain": "youtube.com",
  "category_id": 7,
  "category": "Entertainment & Media",
  "confidence": 0.98,
  "status": "CLASSIFIED",
  "source": "database",
  "reason": "Produced video & multimedia consumption (TB2, F1)"
}
```

### Low-Confidence / Miscellaneous Result (Category 11)
```json
{
  "domain": "unknown-example.com",
  "category_id": 11,
  "category": "Miscellaneous",
  "confidence": 0.61,
  "status": "LOW_CONFIDENCE",
  "source": "llm_categorizer",
  "reason": "Available metadata is insufficient to confidently classify the domain into categories 1-10."
}
```
