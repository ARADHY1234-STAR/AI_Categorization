import asyncio
import os
from pathlib import Path
import pandas as pd
import streamlit as st

# Set page configuration
st.set_page_config(
    page_title="AI Domain Categorization Engine",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Bridge Streamlit Cloud secrets to environment variables if available
if hasattr(st, "secrets"):
    for secret_key in ["OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL", "DATABASE_URL"]:
        try:
            if secret_key in st.secrets and secret_key not in os.environ:
                os.environ[secret_key] = str(st.secrets[secret_key])
        except Exception:
            pass

# Import backend modules
from app.config.settings import get_settings
from app.database.connection import get_db_session, init_db
from app.database.repository import DomainRepository
from app.classifier.pipeline import DomainClassificationPipeline
from app.classifier.bulk import BulkClassifier
from app.models.category import CATEGORIES_REGISTRY, ALLOWED_CATEGORY_NAMES
from app.rules.base import rule_registry

# Initialize database schema on startup
init_db()

# Color mappings for the 10 Categories
CATEGORY_COLORS = {
    "Communication": "#3b82f6",
    "Social Media": "#ec4899",
    "Productivity & Office": "#10b981",
    "Development & IT": "#8b5cf6",
    "Business & Enterprise": "#f59e0b",
    "Research & Learning": "#6366f1",
    "Entertainment & Media": "#f43f5e",
    "Shopping & E-commerce": "#14b8a6",
    "System Utilities & Security": "#06b6d4",
    "File Storage & Data Sharing": "#84cc16",
}

CATEGORY_ICONS = {
    "Communication": "💬",
    "Social Media": "📱",
    "Productivity & Office": "📊",
    "Development & IT": "💻",
    "Business & Enterprise": "🏢",
    "Research & Learning": "📚",
    "Entertainment & Media": "🎬",
    "Shopping & E-commerce": "🛍️",
    "System Utilities & Security": "🛡️",
    "File Storage & Data Sharing": "📁",
}


@st.cache_resource
def get_pipeline():
    """Cache and reuse classification pipeline instance."""
    settings = get_settings()
    pipe = DomainClassificationPipeline(settings=settings)
    bulk = BulkClassifier(pipeline=pipe)
    return pipe, bulk


pipeline, bulk_classifier = get_pipeline()


# --- SIDEBAR ---
with st.sidebar:
    st.title("🌐 AI Categorization")
    st.caption("Hierarchical 2-Layer Classification Engine")

    settings = get_settings()

    # API Key Configuration
    st.subheader("⚙️ System Status")
    api_key_configured = bool(settings.OPENROUTER_API_KEY)
    if api_key_configured:
        st.success("✅ OpenRouter API Key Active", icon="🔑")
    else:
        st.warning("⚠️ No API Key found in env/secrets.", icon="⚠️")
        user_key = st.text_input("Enter OpenRouter Key:", type="password", help="Optional runtime key if not set in environment.")
        if user_key:
            os.environ["OPENROUTER_API_KEY"] = user_key
            st.rerun()

    st.markdown(f"**Model:** `{settings.OPENROUTER_MODEL}`")
    st.markdown(f"**Confidence Threshold:** `{settings.CLASSIFIER_CONFIDENCE_THRESHOLD:.2f}`")
    st.markdown(f"**Locked Rules Loaded:** `{len(rule_registry.list_rules())}`")

    st.divider()

    # Taxonomy quick reference
    st.subheader("📋 10 Fixed Categories")
    for cat_id in sorted(CATEGORIES_REGISTRY.keys()):
        cat = CATEGORIES_REGISTRY[cat_id]
        icon = CATEGORY_ICONS.get(cat.name.value, "📌")
        with st.expander(f"{icon} #{cat.id} {cat.name.value}"):
            st.write(f"**Scope:** {cat.description}")
            st.caption(f"**Examples:** {cat.examples_scope}")

    st.divider()
    st.caption("Built with FastAPI, OpenRouter, SQLite & Streamlit.")


# --- MAIN CONTENT ---
st.title("🌐 AI Domain & Website Categorization Engine")
st.markdown(
    "Accurately classify domains into 10 enterprise categories using strict **two-layer resolution** "
    "(HTTP metadata enrichment + LLM inference with locked business rules **F1 & TB1–TB8**)."
)

tab1, tab2, tab3, tab4 = st.tabs([
    "🎯 Single URL Categorizer",
    "📦 Batch Processing",
    "💾 Stored Database Records",
    "🛡️ Locked Rules Reference",
])


# ==========================================
# TAB 1: SINGLE URL CATEGORIZATION
# ==========================================
with tab1:
    st.subheader("Classify a Website or Subdomain")

    # Example pills
    st.markdown("**Try popular examples:**")
    example_cols = st.columns(6)
    examples = [
        "https://youtube.com",
        "https://docs.google.com",
        "https://drive.google.com",
        "https://slack.com",
        "https://discord.com",
        "https://speedtest.net",
    ]
    
    selected_example = None
    for i, ex in enumerate(examples):
        if example_cols[i].button(ex.replace("https://", ""), key=f"ex_{i}", use_container_width=True):
            selected_example = ex

    url_input = st.text_input(
        "Enter Website URL or Domain:",
        value=selected_example or "",
        placeholder="e.g. https://notion.so, miro.com, or mail.google.com",
    )

    force_refresh = st.checkbox("Bypass Database Cache (Force Live Fetch & AI Inference)", value=False)

    if st.button("🚀 Classify Domain", type="primary", use_container_width=True):
        if not url_input.strip():
            st.error("Please enter a valid domain or URL.")
        else:
            with st.spinner(f"Classifying '{url_input}' via 2-layer pipeline..."):
                try:
                    db = get_db_session()
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(
                        pipeline.classify(raw_input=url_input.strip(), db_session=db, force_refresh=force_refresh)
                    )
                    db.close()

                    st.markdown("---")

                    # Hero Result Card
                    cat_name = result.category or "NEEDS_REVIEW / UNKNOWN"
                    color = CATEGORY_COLORS.get(cat_name, "#6b7280")
                    icon = CATEGORY_ICONS.get(cat_name, "🔍")

                    res_col1, res_col2 = st.columns([1.5, 1])

                    with res_col1:
                        st.markdown(
                            f"""
                            <div style="background: rgba(255, 255, 255, 0.05); border-left: 6px solid {color}; padding: 1.25rem; border-radius: 8px; margin-bottom: 1rem;">
                                <div style="font-size: 0.85rem; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em;">Categorization Result</div>
                                <div style="font-size: 1.8rem; font-weight: 700; color: {color}; margin: 0.25rem 0;">{icon} {cat_name}</div>
                                <div style="font-size: 1.05rem; color: #e5e7eb;"><strong>Domain:</strong> <code>{result.domain}</code></div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        # Reason Box
                        st.info(f"**Classification Rationale:** {result.reason or 'Classified via rule engine.'}")

                    with res_col2:
                        # Metrics Card
                        conf_pct = int(result.confidence * 100)
                        st.metric("Confidence Score", f"{result.confidence:.2f} ({conf_pct}%)")
                        st.progress(result.confidence)

                        m_c1, m_c2 = st.columns(2)
                        m_c1.metric("Resolution Source", result.source.replace("_", " ").title())
                        m_c2.metric("Pipeline Status", result.status)

                    # Metadata Breakdown Expander
                    with st.expander("🔍 Layer 1 & 2 Execution Details", expanded=True):
                        d_c1, d_c2, d_c3 = st.columns(3)
                        d_c1.markdown(f"**Rule Applied:** `{result.rule_applied or 'General Taxonomy'}`")
                        d_c2.markdown(f"**Subdomain Isolated:** `{result.subdomain or 'None (Root Domain)'}`")
                        d_c3.markdown(f"**HTTP Enrichment Used:** `{'Yes (Live Fetched)' if result.enrichment_used else 'No (Bypassed / Cached)'}`")

                        if result.metadata_used:
                            st.markdown("**Extracted Webpage Metadata:**")
                            st.json(result.metadata_used)

                except Exception as e:
                    st.error(f"Classification failed: {e}")


# ==========================================
# TAB 2: BATCH CLASSIFICATION
# ==========================================
with tab2:
    st.subheader("Bulk Domain Categorization")
    st.markdown("Classify multiple domains simultaneously with automatic deduplication and concurrency control.")

    batch_input_mode = st.radio("Input Method:", ["Text Area (Paste URLs)", "CSV File Upload"], horizontal=True)

    domains_to_process = []
    if batch_input_mode == "Text Area (Paste URLs)":
        raw_text = st.text_area(
            "Paste domain names or URLs (one per line):",
            height=150,
            value="youtube.com\nhttps://docs.google.com\nslack.com\ntrello.com\nhttps://wetransfer.com\nhttps://salesforce.com",
        )
        if raw_text.strip():
            domains_to_process = [line.strip() for line in raw_text.splitlines() if line.strip()]
    else:
        uploaded_file = st.file_uploader("Upload CSV file (must contain a 'url' or 'domain' column):", type=["csv"])
        if uploaded_file:
            df_upload = pd.read_csv(uploaded_file)
            col_candidates = [c for c in df_upload.columns if "domain" in c.lower() or "url" in c.lower() or "website" in c.lower()]
            target_col = col_candidates[0] if col_candidates else df_upload.columns[0]
            st.info(f"Using column **'{target_col}'** for classification.")
            domains_to_process = df_upload[target_col].dropna().astype(str).tolist()

    if st.button("⚡ Run Batch Classification", type="primary", disabled=not domains_to_process):
        with st.spinner(f"Processing {len(domains_to_process)} domain rows..."):
            try:
                db = get_db_session()
                items = [{"domain": d} for d in domains_to_process]

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                results, summary = loop.run_until_complete(
                    bulk_classifier.process_items(items, db_session=db)
                )
                db.close()

                st.success(
                    f"Batch complete: {len(results)} rows processed in {summary.get('duration_seconds', 0):.2f}s "
                    f"({summary.get('cached_hits', 0)} DB cache hits, {summary.get('override_hits', 0)} brand overrides)."
                )

                # Format DataFrame for display
                table_data = []
                for r in results:
                    table_data.append({
                        "Input Domain": r.original_url,
                        "FQDN": r.domain,
                        "Subdomain": r.subdomain or "—",
                        "Category": r.category or "NEEDS_REVIEW",
                        "Category ID": r.category_id or "—",
                        "Confidence": f"{r.confidence:.2f}",
                        "Source": r.source,
                        "Rule": r.rule_applied or "—",
                        "Status": r.status,
                        "Reason": r.reason,
                    })

                df_results = pd.DataFrame(table_data)
                st.dataframe(df_results, use_container_width=True)

                # Download CSV button
                csv_data = df_results.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Categorization Results (CSV)",
                    data=csv_data,
                    file_name="categorization_results.csv",
                    mime="text/csv",
                )

            except Exception as e:
                st.error(f"Batch processing error: {e}")


# ==========================================
# TAB 3: DATABASE RECORDS
# ==========================================
with tab3:
    st.subheader("Stored Domain Classifications (Database)")
    st.caption("Active SQLite cache and human override registry.")

    db_search = st.text_input("Search stored domains or categories:", "")

    db = get_db_session()
    repo = DomainRepository(db)
    from app.database.models import DomainClassificationModel

    query = db.query(DomainClassificationModel)
    if db_search.strip():
        s = f"%{db_search.strip()}%"
        query = query.filter(
            (DomainClassificationModel.fqdn.ilike(s)) |
            (DomainClassificationModel.category_name.ilike(s)) |
            (DomainClassificationModel.classification_source.ilike(s))
        )
    
    total_db_records = query.count()
    records = query.order_by(DomainClassificationModel.id.desc()).limit(100).all()
    db.close()

    st.markdown(f"Showing **{len(records)}** of **{total_db_records}** stored domain classifications:")

    if records:
        db_rows = []
        for r in records:
            db_rows.append({
                "ID": r.id,
                "Domain (FQDN)": r.fqdn,
                "Subdomain": r.normalized_subdomain or "—",
                "Category": r.category_name or "—",
                "Confidence": f"{r.confidence:.2f}",
                "Source": r.classification_source,
                "Rule": r.rule_applied or "—",
                "Status": r.status,
                "Human Override": "Yes" if r.is_human_override else "No",
                "Reason": r.reason,
            })
        st.dataframe(pd.DataFrame(db_rows), use_container_width=True)
    else:
        st.info("No matching records found in database.")


# ==========================================
# TAB 4: LOCKED RULES REFERENCE
# ==========================================
with tab4:
    st.subheader("🛡️ Locked Business Rules & Tie-Breakers (F1, TB1–TB8)")
    st.markdown("These rules are deterministically injected into the AI prompt and override table to enforce consistency.")

    rules = rule_registry.list_rules(sorted_by_precedence=True)
    for rule in rules:
        with st.expander(f"📌 **{rule.rule_id}**: {rule.name} (Precedence: {rule.precedence})", expanded=True):
            st.markdown(f"**Scope:** `{rule.scope.value}`")
            st.markdown(f"**Description:** {rule.description}")
            st.info(f"**Prompt Instruction:** \"{rule.prompt_instruction}\"")
