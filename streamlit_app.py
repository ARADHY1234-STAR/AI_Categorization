import asyncio
import html
import os
from pathlib import Path
import pandas as pd
import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="Domain Categorization AI — Classification & Governance Dashboard",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 2. Bridge Streamlit Cloud Secrets to Environment
if hasattr(st, "secrets"):
    for secret_key in ["OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL", "DATABASE_URL"]:
        try:
            if secret_key in st.secrets and secret_key not in os.environ:
                os.environ[secret_key] = str(st.secrets[secret_key])
        except Exception:
            pass

# 3. Import Backend Architecture
from app.config.settings import get_settings
from app.database.connection import get_db_session, init_db
from app.database.models import DomainClassificationModel
from app.database.repository import DomainRepository
from app.classifier.pipeline import DomainClassificationPipeline
from app.classifier.bulk import BulkClassifier
from app.models.category import CATEGORIES_REGISTRY, ALLOWED_CATEGORY_NAMES, get_category_id_by_name
from app.models.schemas import ClassificationSource, ClassificationStatus
from app.normalization.normalizer import normalize_domain
from app.rules.base import rule_registry

# Initialize SQLite database schema
init_db()

# 4. Color & Icon Taxonomy
CATEGORY_COLORS = {
    "Communication": "#3b82f6",
    "Social Media": "#ec4899",
    "Productivity & Office": "#10b981",
    "Development & IT": "#6366f1",
    "Business & Enterprise": "#f59e0b",
    "Research & Learning": "#8b5cf6",
    "Entertainment & Media": "#ef4444",
    "Shopping & E-commerce": "#f97316",
    "System Utilities & Security": "#06b6d4",
    "File Storage & Data Sharing": "#14b8a6",
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


# 5. Inject Exact Theme CSS matching app/static/style.css
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap');

      /* Hide Default Streamlit Chrome & Headers */
      #MainMenu, header[data-testid="stHeader"], footer, div[data-testid="stDecoration"], .stDeployButton, button[title="View fullscreen"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
      }

      /* Global Layout & Theme */
      .stApp {
        background-color: #0b0f19 !important;
        color: #f9fafb !important;
        font-family: 'Outfit', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        background-image: 
          radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.12) 0%, transparent 40%),
          radial-gradient(circle at 85% 85%, rgba(6, 182, 212, 0.1) 0%, transparent 40%),
          radial-gradient(circle at 50% 50%, rgba(168, 85, 247, 0.05) 0%, transparent 60%) !important;
        background-attachment: fixed !important;
      }

      .main .block-container {
        max-width: 1380px !important;
        padding-top: 1rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
      }

      /* Custom Navbar */
      .custom-navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.1rem 1.75rem;
        background: rgba(11, 15, 25, 0.85);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
      }

      .nav-brand {
        display: flex;
        align-items: center;
        gap: 0.9rem;
      }

      .brand-icon {
        width: 44px;
        height: 44px;
        background: linear-gradient(135deg, #6366f1, #06b6d4);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.4rem;
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.4);
      }

      .brand-title {
        font-size: 1.35rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #ffffff, #c7d2fe);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
      }

      .brand-subtitle {
        font-size: 0.75rem;
        color: #06b6d4;
        font-weight: 600;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }

      .nav-status {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 0.95rem;
        border-radius: 9999px;
        background: rgba(16, 185, 129, 0.12);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #34d399;
        font-size: 0.8rem;
        font-weight: 700;
      }

      .status-dot {
        width: 8px;
        height: 8px;
        background: #10b981;
        border-radius: 50%;
        box-shadow: 0 0 8px #10b981;
        animation: pulse-dot 2s infinite;
      }

      @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.4; transform: scale(0.85); }
      }

      /* Streamlit Tab Styling Overrides */
      .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
        padding-bottom: 0.5rem !important;
        background: transparent !important;
      }

      .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border: none !important;
        color: #9ca3af !important;
        font-family: 'Outfit', sans-serif !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        padding: 0.65rem 1.15rem !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
      }

      .stTabs [data-baseweb="tab"]:hover {
        color: #f9fafb !important;
        background: rgba(255, 255, 255, 0.04) !important;
      }

      .stTabs [aria-selected="true"] {
        color: #ffffff !important;
        background: rgba(99, 102, 241, 0.18) !important;
        border: 1px solid rgba(99, 102, 241, 0.35) !important;
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.25) !important;
      }

      /* Glass Panels */
      .glass-card {
        background: rgba(17, 24, 39, 0.75);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 18px;
        padding: 1.5rem 1.75rem;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        margin-bottom: 1.25rem;
      }

      .glass-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 0.9rem;
        margin-bottom: 1.25rem;
      }

      .glass-card-title {
        font-size: 1.15rem;
        font-weight: 700;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #ffffff;
      }

      .glass-card-subtitle {
        font-size: 0.82rem;
        color: #9ca3af;
        margin-top: 0.2rem;
      }

      /* Form inputs styling */
      .stTextInput > div > div > input,
      .stTextArea > div > div > textarea,
      .stSelectbox > div > div {
        background: rgba(15, 23, 42, 0.65) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
        color: #f9fafb !important;
        font-family: 'Outfit', 'Inter', sans-serif !important;
        font-size: 0.95rem !important;
        transition: all 0.2s !important;
      }

      .stTextInput > div > div > input:focus,
      .stTextArea > div > div > textarea:focus {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
        background: rgba(15, 23, 42, 0.9) !important;
      }

      /* Streamlit Buttons */
      .stButton > button {
        background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 12px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        padding: 0.75rem 1.5rem !important;
        box-shadow: 0 4px 15px rgba(79, 70, 229, 0.35) !important;
        transition: all 0.25s ease !important;
      }

      .stButton > button:hover {
        background: linear-gradient(135deg, #4f46e5, #4338ca) !important;
        box-shadow: 0 6px 20px rgba(79, 70, 229, 0.5) !important;
        transform: translateY(-1px) !important;
      }

      /* Category Hero Card */
      .category-hero {
        padding: 1.5rem;
        border-radius: 14px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        position: relative;
        overflow: hidden;
        margin-bottom: 1rem;
      }

      .category-hero-bar {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
      }

      .category-header-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.5rem;
      }

      .cat-id-pill {
        font-size: 0.75rem;
        font-weight: 700;
        padding: 0.2rem 0.55rem;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.1);
        color: #9ca3af;
      }

      .category-name-display {
        font-size: 1.6rem;
        font-weight: 800;
        letter-spacing: -0.01em;
        margin: 0.2rem 0;
      }

      .domain-display {
        font-size: 0.95rem;
        color: #9ca3af;
        display: flex;
        align-items: center;
        gap: 0.4rem;
        margin-top: 0.25rem;
        word-break: break-all;
      }

      /* Metadata Tags Grid */
      .meta-tags-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.75rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
      }

      @media (max-width: 768px) {
        .meta-tags-grid {
          grid-template-columns: 1fr;
        }
      }

      .meta-box {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
      }

      .meta-box-label {
        font-size: 0.7rem;
        font-weight: 700;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
      }

      .meta-box-value {
        font-size: 0.88rem;
        font-weight: 700;
        color: #f9fafb;
      }

      /* Source Pills */
      .source-pill {
        padding: 0.22rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        display: inline-block;
      }
      .source-database { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); }
      .source-brand_override { background: rgba(236, 72, 153, 0.15); color: #f472b6; border: 1px solid rgba(236, 72, 153, 0.3); }
      .source-llm_categorizer { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
      .source-human_override { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }

      /* Confidence Bar */
      .confidence-meter {
        margin-top: 0.75rem;
      }
      .confidence-bar-bg {
        height: 6px;
        background: rgba(255, 255, 255, 0.08);
        border-radius: 3px;
        overflow: hidden;
        margin-top: 0.35rem;
      }
      .confidence-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #3b82f6, #10b981);
        border-radius: 3px;
      }

      /* Reason Box */
      .reason-box {
        background: rgba(15, 23, 42, 0.6);
        border-left: 4px solid #6366f1;
        border-radius: 0 10px 10px 0;
        padding: 0.9rem 1.1rem;
        font-size: 0.88rem;
        color: #d1d5db;
        line-height: 1.5;
        margin-top: 0.75rem;
      }

      /* Categories Grid */
      .categories-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
        gap: 1.25rem;
      }

      .category-card {
        padding: 1.25rem;
        border-radius: 14px;
        background: rgba(17, 24, 39, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        position: relative;
        overflow: hidden;
        transition: all 0.2s ease;
      }

      .category-card:hover {
        transform: translateY(-2px);
        border-color: rgba(255, 255, 255, 0.2);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
      }

      /* Rules Item */
      .rule-item {
        padding: 1.25rem 1.5rem;
        border-radius: 14px;
        background: rgba(17, 24, 39, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-left: 4px solid #6366f1;
        margin-bottom: 1rem;
      }

      .rule-id-badge {
        font-weight: 800;
        font-size: 0.85rem;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        background: rgba(99, 102, 241, 0.2);
        color: #a5b4fc;
      }

      /* Empty State Box */
      .result-placeholder {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 3.5rem 1.5rem;
        text-align: center;
        color: #6b7280;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# 6. Render Custom Navbar
st.markdown(
    """
    <div class="custom-navbar">
      <div class="nav-brand">
        <div class="brand-icon">🌐</div>
        <div>
          <div class="brand-title">Domain Categorization AI</div>
          <div class="brand-subtitle">Hierarchical Classifier & Governance Dashboard</div>
        </div>
      </div>
      <div style="display: flex; align-items: center; gap: 1rem;">
        <div class="nav-status">
          <span class="status-dot"></span>
          <span>Pipeline Active</span>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 7. Main Dashboard Tabs
tab_play, tab_batch, tab_cats, tab_rules, tab_override, tab_db = st.tabs([
    "🎯 Live Classifier",
    "📦 Bulk Batch Tester",
    "📋 10 Fixed Categories",
    "🛡️ Locked Rules (F1, TB1–TB8)",
    "👤 Human Override",
    "💾 Database Records",
])


# ==========================================
# TAB 1: LIVE CLASSIFIER PLAYGROUND
# ==========================================
with tab_play:
    col_input, col_result = st.columns([1.1, 0.9], gap="large")

    with col_input:
        st.markdown(
            """
            <div class="glass-card-header" style="margin-bottom: 0.75rem;">
              <div>
                <div class="glass-card-title"><span>🎯</span> Classify Domain / Subdomain</div>
                <div class="glass-card-subtitle">Real-time normalization, HTTP enrichment, and LLM rule reasoning</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Example buttons
        st.caption("Quick Test Examples:")
        ex_cols = st.columns(4)
        selected_url = None
        if ex_cols[0].button("YouTube", key="btn_yt", use_container_width=True):
            selected_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        if ex_cols[1].button("Google Docs", key="btn_docs", use_container_width=True):
            selected_url = "https://docs.google.com/document/d/123"
        if ex_cols[2].button("Google Drive", key="btn_drive", use_container_width=True):
            selected_url = "https://drive.google.com/drive/u/0"
        if ex_cols[3].button("Discord", key="btn_discord", use_container_width=True):
            selected_url = "https://discord.com"

        ex_cols2 = st.columns(4)
        if ex_cols2[0].button("Reddit", key="btn_reddit", use_container_width=True):
            selected_url = "https://reddit.com/r/technology"
        if ex_cols2[1].button("Salesforce", key="btn_sfdc", use_container_width=True):
            selected_url = "https://salesforce.com"
        if ex_cols2[2].button("Slack", key="btn_slack", use_container_width=True):
            selected_url = "https://slack.com"
        if ex_cols2[3].button("Speedtest", key="btn_speed", use_container_width=True):
            selected_url = "https://speedtest.net"

        # Form Inputs
        target_url = st.text_input(
            "Website Domain or URL",
            value=selected_url or (st.session_state.get("target_url", "") if not selected_url else ""),
            placeholder="e.g. https://notion.so, miro.com, or mail.google.com",
            key="input_target_url",
        )

        with st.expander("⚙️ Optional Parameters & Controls", expanded=False):
            custom_subdomain = st.text_input("Explicit Subdomain (Optional)", placeholder="e.g. docs, drive, mail")
            custom_app_name = st.text_input("Application / Brand Name (Optional)", placeholder="e.g. Notion Workspace")
            force_refresh = st.checkbox("Bypass Database Cache (Force Live Fetch & AI Inference)", value=False)

        submit_btn = st.button("🚀 Classify Domain", type="primary", use_container_width=True)

    with col_result:
        st.markdown(
            """
            <div class="glass-card-header" style="margin-bottom: 0.75rem;">
              <div>
                <div class="glass-card-title"><span>📊</span> Classification Result</div>
                <div class="glass-card-subtitle">Real-time pipeline outcome and metadata</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Trigger Classification if clicked or example selected
        run_classify = submit_btn or bool(selected_url)
        input_to_run = target_url.strip() if target_url else (selected_url.strip() if selected_url else "")

        if run_classify and input_to_run:
            with st.spinner(f"Classifying '{input_to_run}' via 2-layer pipeline..."):
                try:
                    db = get_db_session()
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    res = loop.run_until_complete(
                        pipeline.classify(
                            raw_input=input_to_run,
                            subdomain=custom_subdomain.strip() if custom_subdomain else None,
                            app_name=custom_app_name.strip() if custom_app_name else None,
                            db_session=db,
                            force_refresh=force_refresh,
                        )
                    )
                    db.close()

                    cat_name = res.category or "NEEDS_REVIEW"
                    color = CATEGORY_COLORS.get(cat_name, "#6366f1")
                    icon = CATEGORY_ICONS.get(cat_name, "🔍")
                    conf_pct = int(res.confidence * 100)
                    src_class = f"source-{res.source}"

                    # Render Category Hero Box
                    st.markdown(
                        f"""
                        <div class="category-hero">
                          <div class="category-hero-bar" style="background: {color}; box-shadow: 0 0 12px {color};"></div>
                          <div class="category-header-top">
                            <span class="cat-id-pill">Category ID: #{res.category_id or '—'}</span>
                            <span class="source-pill {src_class}">{res.source.replace('_', ' ').title()}</span>
                          </div>
                          <div class="category-name-display" style="color: {color};">{icon} {html.escape(cat_name)}</div>
                          <div class="domain-display">
                            <span>🌐</span>
                            <span>{html.escape(res.domain)}</span>
                          </div>
                          <div class="confidence-meter">
                            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #9ca3af;">
                              <span>Confidence Score</span>
                              <strong style="color: #f9fafb;">{res.confidence:.2f} ({conf_pct}%)</strong>
                            </div>
                            <div class="confidence-bar-bg">
                              <div class="confidence-bar-fill" style="width: {conf_pct}%;"></div>
                            </div>
                          </div>
                        </div>

                        <div class="meta-tags-grid">
                          <div class="meta-box">
                            <div class="meta-box-label">Rule Applied</div>
                            <div class="meta-box-value">{html.escape(res.rule_applied or 'F1 / General')}</div>
                          </div>
                          <div class="meta-box">
                            <div class="meta-box-label">HTTP Enrichment</div>
                            <div class="meta-box-value">{'Yes (Live Fetched)' if res.enrichment_used else 'No (Bypassed / Cached)'}</div>
                          </div>
                          <div class="meta-box">
                            <div class="meta-box-label">Subdomain Split</div>
                            <div class="meta-box-value">{html.escape(res.subdomain or 'Root Domain')}</div>
                          </div>
                        </div>

                        <div class="reason-box">
                          <strong>Reasoning: </strong>
                          <span>{html.escape(res.reason or 'Classified via rule engine.')}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Extracted Web Evidence Expander
                    if res.metadata_used:
                        with st.expander("🔍 Extracted Web Evidence (Layer 1 Metadata)", expanded=False):
                            st.json(res.metadata_used)

                except Exception as e:
                    st.error(f"Classification failed: {e}")

        else:
            # Empty State Placeholder
            st.markdown(
                """
                <div class="result-placeholder">
                  <div style="font-size: 2.5rem; margin-bottom: 0.75rem; opacity: 0.5;">⚡</div>
                  <p style="font-size: 0.95rem;">Enter a domain or click one of the quick test examples on the left to trigger the classification pipeline.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ==========================================
# TAB 2: BULK BATCH TESTER
# ==========================================
with tab_batch:
    st.markdown(
        """
        <div class="glass-card-header">
          <div>
            <div class="glass-card-title"><span>📦</span> High-Throughput Batch Deduplication Tester</div>
            <div class="glass-card-subtitle">Paste multiple domains or upload a CSV to test pre-classification deduplication & concurrency</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    batch_mode = st.radio("Input Method:", ["Text Area (Paste URLs)", "CSV File Upload"], horizontal=True)

    domains_to_process = []
    if batch_mode == "Text Area (Paste URLs)":
        default_batch = (
            "https://www.youtube.com/watch?v=1\n"
            "https://www.youtube.com/watch?v=2\n"
            "youtube.com\n"
            "https://docs.google.com/document/d/1\n"
            "https://drive.google.com/drive/u/0\n"
            "discord.com\n"
            "telegram.org\n"
            "https://github.com/torvalds/linux\n"
            "salesforce.com"
        )
        batch_text = st.text_area("Paste domains or URLs (one per line):", height=160, value=default_batch)
        if batch_text.strip():
            domains_to_process = [line.strip() for line in batch_text.splitlines() if line.strip()]
    else:
        uploaded_csv = st.file_uploader("Upload CSV file:", type=["csv"])
        if uploaded_csv:
            df_up = pd.read_csv(uploaded_csv)
            col_candidates = [c for c in df_up.columns if "domain" in c.lower() or "url" in c.lower() or "website" in c.lower()]
            target_col = col_candidates[0] if col_candidates else df_up.columns[0]
            st.info(f"Using column **'{target_col}'** for batch processing.")
            domains_to_process = df_up[target_col].dropna().astype(str).tolist()

    if st.button("⚡ Process Batch with Deduplication", type="primary", disabled=not domains_to_process):
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
                    f"✅ Processed {len(results)} rows in {summary.get('duration_seconds', 0):.2f}s "
                    f"({summary.get('cached_hits', 0)} DB hits, {summary.get('override_hits', 0)} brand overrides, "
                    f"{summary.get('llm_calls', 0)} live LLM inferences)."
                )

                # Format DataFrame Table
                table_rows = []
                for idx, r in enumerate(results, start=1):
                    table_rows.append({
                        "#": idx,
                        "Normalized FQDN": r.domain,
                        "Subdomain": r.subdomain or "—",
                        "Category": r.category or "NEEDS_REVIEW",
                        "Category ID": r.category_id or "—",
                        "Confidence": f"{r.confidence:.2f}",
                        "Source": r.source,
                        "Rule": r.rule_applied or "—",
                        "Status": r.status,
                        "Reason": r.reason,
                    })

                df_out = pd.DataFrame(table_rows)
                st.dataframe(df_out, use_container_width=True)

                csv_bytes = df_out.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Results CSV",
                    data=csv_bytes,
                    file_name="batch_categorization_results.csv",
                    mime="text/csv",
                )

            except Exception as e:
                st.error(f"Batch processing error: {e}")


# ==========================================
# TAB 3: 10 FIXED CATEGORIES REFERENCE
# ==========================================
with tab_cats:
    st.markdown(
        """
        <div class="glass-card-header">
          <div>
            <div class="glass-card-title"><span>📋</span> The 10-Category Fixed Taxonomy</div>
            <div class="glass-card-subtitle">Every website is strictly classified into exactly one of these 10 categories</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cats_html = '<div class="categories-grid">'
    for cat_id in sorted(CATEGORIES_REGISTRY.keys()):
        cat = CATEGORIES_REGISTRY[cat_id]
        cat_name = cat.name.value
        color = CATEGORY_COLORS.get(cat_name, "#6366f1")
        icon = CATEGORY_ICONS.get(cat_name, "📌")

        cats_html += f"""
        <div class="category-card" style="border-top: 4px solid {color};">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 1.3rem;">{icon}</span>
            <span class="cat-id-pill">ID #{cat.id}</span>
          </div>
          <div style="font-size: 1.1rem; font-weight: 700; color: {color};">{html.escape(cat_name)}</div>
          <div style="font-size: 0.82rem; color: #9ca3af; line-height: 1.4;">{html.escape(cat.description)}</div>
          <div style="font-size: 0.75rem; color: #6b7280; background: rgba(0,0,0,0.3); padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: auto;">
            <strong>Examples:</strong> {html.escape(cat.examples_scope)}
          </div>
        </div>
        """
    cats_html += '</div>'
    st.markdown(cats_html, unsafe_allow_html=True)


# ==========================================
# TAB 4: LOCKED RULES REFERENCE (F1, TB1–TB8)
# ==========================================
with tab_rules:
    st.markdown(
        """
        <div class="glass-card-header">
          <div>
            <div class="glass-card-title"><span>🛡️</span> Locked Business Rules & Tie-Breakers (F1, TB1–TB8)</div>
            <div class="glass-card-subtitle">Auditable, versioned rules injected directly into the LLM system prompt</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rules = rule_registry.list_rules(sorted_by_precedence=True)
    for rule in rules:
        st.markdown(
            f"""
            <div class="rule-item">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                <div>
                  <span class="rule-id-badge">{rule.rule_id}</span>
                  <strong style="font-size: 1.05rem; margin-left: 0.5rem; color: #f9fafb;">{html.escape(rule.name)}</strong>
                </div>
                <span style="font-size: 0.75rem; color: #9ca3af;">Scope: {rule.scope.value} | Precedence: {rule.precedence}</span>
              </div>
              <div style="font-size: 0.85rem; color: #9ca3af; margin-bottom: 0.5rem;">{html.escape(rule.description)}</div>
              <div style="font-size: 0.82rem; color: #c7d2fe; background: rgba(0, 0, 0, 0.25); padding: 0.65rem 0.9rem; border-radius: 8px;">
                <strong>Prompt Instruction:</strong> "{html.escape(rule.prompt_instruction)}"
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==========================================
# TAB 5: HUMAN OVERRIDE
# ==========================================
with tab_override:
    st.markdown(
        """
        <div class="glass-card-header">
          <div>
            <div class="glass-card-title"><span>👤</span> Create Human Override Record</div>
            <div class="glass-card-subtitle">Set an immutable classification that cannot be overwritten by AI</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("human_override_form"):
        h_domain = st.text_input("Domain or URL:", placeholder="e.g. internal-portal.mycompany.com")
        h_category = st.selectbox("Select One of the 10 Categories:", [""] + ALLOWED_CATEGORY_NAMES)
        h_reason = st.text_input("Reviewer / Audit Reason:", value="Manually verified by human reviewer")
        h_submit = st.form_submit_submit_button = st.form_submit_button("💾 Save Protected Human Override", type="primary")

        if h_submit:
            if not h_domain.strip() or not h_category:
                st.error("Please provide both a valid domain and a target category.")
            else:
                try:
                    db = get_db_session()
                    norm = normalize_domain(h_domain.strip())
                    repo = DomainRepository(db)
                    record = repo.save_classification(
                        norm=norm,
                        category=h_category,
                        confidence=1.0,
                        source=ClassificationSource.HUMAN_OVERRIDE,
                        status="OVERRIDE",
                        is_human_override=True,
                        original_url=h_domain.strip(),
                        final_url=h_domain.strip(),
                        metadata_fetch_status="HUMAN_OVERRIDE",
                        reason=h_reason.strip(),
                    )
                    db.close()
                    st.success(f"✅ Successfully created protected human override for **{norm.fqdn}** → **{h_category}**.")
                except Exception as ex:
                    st.error(f"Failed to save human override: {ex}")


# ==========================================
# TAB 6: DATABASE RECORDS
# ==========================================
with tab_db:
    st.markdown(
        """
        <div class="glass-card-header">
          <div>
            <div class="glass-card-title"><span>💾</span> Stored Domain Classifications (Database Table)</div>
            <div class="glass-card-subtitle">Active SQLite persistent cache and human overrides (File: data/domains.db)</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    db_search = st.text_input("Search stored domains or categories:", placeholder="Search by domain, category, or source...", key="db_search_bar")

    db = get_db_session()
    query = db.query(DomainClassificationModel)
    if db_search.strip():
        s = f"%{db_search.strip()}%"
        query = query.filter(
            (DomainClassificationModel.fqdn.ilike(s)) |
            (DomainClassificationModel.category_name.ilike(s)) |
            (DomainClassificationModel.classification_source.ilike(s))
        )

    total_count = query.count()
    records = query.order_by(DomainClassificationModel.id.desc()).limit(150).all()
    db.close()

    st.caption(f"Showing **{len(records)}** of **{total_count}** stored records in SQLite database:")

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
                "Reason": r.reason or "—",
            })
        st.dataframe(pd.DataFrame(db_rows), use_container_width=True)
    else:
        st.info("No matching database records found.")
