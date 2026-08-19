from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.connection import get_db_session, init_db
from app.database.repository import DomainRepository
from app.classifier.pipeline import DomainClassificationPipeline
from app.classifier.bulk import BulkClassifier
from app.models.category import CATEGORIES_REGISTRY, ALLOWED_CATEGORY_NAMES, get_category_id_by_name
from app.models.schemas import (
    BatchClassifyRequest,
    ClassificationResponse,
    ClassificationSource,
    ClassifyRequest,
)
from app.normalization.normalizer import normalize_domain
from app.rules.base import rule_registry

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema on startup
    init_db()
    yield


app = FastAPI(
    title="Domain Categorization AI Service",
    description="Internal backend service for classifying website domains into 10 fixed categories.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static assets
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_dashboard():
    """Serve custom web frontend dashboard."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Frontend static files not found. Visit /docs for API documentation."}


# Dependency for DB Session
def get_db():
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()


pipeline = DomainClassificationPipeline()
bulk_classifier = BulkClassifier(pipeline=pipeline)


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "Domain Categorization AI",
        "model": get_settings().OPENROUTER_MODEL,
        "rules_count": len(rule_registry.list_rules()),
    }


@app.get("/rules", tags=["Rules Engine"])
def get_rules():
    """List all registered business rules and active brand overrides."""
    rules = [
        {
            "rule_id": r.rule_id,
            "name": r.name,
            "scope": r.scope.value,
            "precedence": r.precedence,
            "description": r.description,
            "instruction": r.prompt_instruction,
        }
        for r in rule_registry.list_rules(sorted_by_precedence=True)
    ]
    overrides = [
        {"domain": k, "category": v.category, "reason": v.reason}
        for k, v in pipeline.override_engine._overrides.items()
    ]
    return {
        "locked_rules": rules,
        "brand_overrides": overrides,
    }


@app.get("/categories", tags=["Categories"])
def get_categories():
    """List the 10 fixed categories."""
    return [
        {
            "id": cat.id,
            "name": cat.name.value,
            "description": cat.description,
            "examples": cat.examples_scope,
        }
        for cat in sorted(CATEGORIES_REGISTRY.values(), key=lambda c: c.id)
    ]


@app.post("/classify", response_model=ClassificationResponse, tags=["Classification"])
async def classify_single_domain(
    request: ClassifyRequest,
    db: Session = Depends(get_db),
):
    """Classify a single domain or subdomain using the hierarchical pipeline."""
    try:
        return await pipeline.classify(
            raw_input=request.domain,
            subdomain=request.subdomain,
            app_name=request.app_name,
            db_session=db,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")


@app.post("/classify/batch", response_model=List[ClassificationResponse], tags=["Classification"])
async def classify_batch_domains(
    request: BatchClassifyRequest,
    db: Session = Depends(get_db),
):
    """Batch classify a list of domains with deduplication and concurrency control."""
    items = []
    for i, d in enumerate(request.domains):
        app_name = (
            request.app_names[i]
            if request.app_names and i < len(request.app_names)
            else None
        )
        items.append({"domain": d, "app_name": app_name})

    results, summary = await bulk_classifier.process_items(items, db_session=db)
    return results


@app.post("/override/human", tags=["Overrides"])
def set_human_override(
    domain: str,
    category: str,
    reason: str = "Manually verified by human reviewer",
    db: Session = Depends(get_db),
):
    """Create or update a human override record that cannot be overwritten by AI."""
    if category not in ALLOWED_CATEGORY_NAMES:
        raise HTTPException(
            status_code=400,
            detail=f"Category '{category}' is invalid. Allowed categories: {ALLOWED_CATEGORY_NAMES}",
        )

    norm = normalize_domain(domain)
    repo = DomainRepository(db)
    record = repo.save_classification(
        norm=norm,
        category=category,
        confidence=1.0,
        source=ClassificationSource.HUMAN_OVERRIDE,
        status="OVERRIDE",
        is_human_override=True,
        original_url=domain,
        final_url=domain,
        metadata_fetch_status="HUMAN_OVERRIDE",
        reason=reason,
    )
    return repo.to_response(record)


@app.post("/database/seed", tags=["Database"])
def seed_default_dataset():
    """Seed the database with default verified domain classifications across all 10 categories."""
    from scripts.seed_database import seed_database
    count = seed_database(verbose=False)
    return {
        "status": "success",
        "message": f"Successfully seeded {count} verified domain classifications into the database.",
        "count": count,
    }


@app.get("/database/records", tags=["Database"])
def list_database_records(
    search: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Retrieve all classified domains stored in the SQLite database."""
    from app.database.models import DomainClassificationModel
    query = db.query(DomainClassificationModel)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (DomainClassificationModel.fqdn.ilike(s)) |
            (DomainClassificationModel.category_name.ilike(s)) |
            (DomainClassificationModel.classification_source.ilike(s))
        )
    total = query.count()
    records = query.order_by(DomainClassificationModel.id.asc()).offset(offset).limit(limit).all()
    repo = DomainRepository(db)
    return {
        "total": total,
        "records": [repo.to_response(r) for r in records],
    }


@app.delete("/database/records/{domain}", tags=["Database"])
def delete_database_record(
    domain: str,
    db: Session = Depends(get_db),
):
    """Delete a domain classification record from the SQLite database."""
    norm = normalize_domain(domain)
    repo = DomainRepository(db)
    deleted = repo.delete_by_fqdn(norm.fqdn)
    if not deleted:
        deleted = repo.delete_by_fqdn(domain)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found in database.")
    return {"status": "success", "message": f"Domain '{norm.fqdn}' deleted from database."}



