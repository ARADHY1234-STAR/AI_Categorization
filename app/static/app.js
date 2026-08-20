// DOM Elements & State
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initPlayground();
  initBatch();
  initHumanOverride();
  initSeedButton();
  initDatabaseView();
  loadCategories();
  loadRules();
  checkHealth();
});

function initSeedButton() {
  const btn = document.getElementById("btn-seed-data");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    const origHtml = btn.innerHTML;
    btn.innerHTML = "<span>⏳</span> Seeding...";
    try {
      const res = await fetch("/database/seed", { method: "POST" });
      if (!res.ok) throw new Error("Failed to seed database");
      const data = await res.json();
      alert(`🌱 ${data.message}`);
    } catch (e) {
      alert("Error seeding database: " + e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  });
}


// Category Colors Map
const CATEGORY_COLORS = {
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
  "Miscellaneous": "#64748b",
};

// 1. Tab Switching
function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(btn => {
    btn.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");
    });
  });
}

// 2. Health & Status
async function checkHealth() {
  try {
    const res = await fetch("/health");
    if (res.ok) {
      const data = await res.json();
      document.getElementById("service-status-text").textContent = `Online • ${data.model || "Ready"}`;
    }
  } catch (e) {
    document.getElementById("service-status-text").textContent = "Connecting...";
  }
}

// 3. Single Domain Playground
function initPlayground() {
  const form = document.getElementById("classify-form");
  const domainInput = document.getElementById("domain-input");
  const subdomainInput = document.getElementById("subdomain-input");
  const appNameInput = document.getElementById("app-name-input");
  const btnSpinner = document.getElementById("btn-spinner");
  const btnText = document.getElementById("btn-text");
  const btnSubmit = document.getElementById("btn-classify");

  // Quick fill pills
  document.querySelectorAll(".pill-btn").forEach(pill => {
    pill.addEventListener("click", () => {
      domainInput.value = pill.getAttribute("data-fill") || "";
      appNameInput.value = pill.getAttribute("data-app") || "";
      subdomainInput.value = "";
      domainInput.focus();
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const rawDomain = domainInput.value.trim();
    if (!rawDomain) return;

    btnSubmit.disabled = true;
    btnSpinner.style.display = "inline-block";
    btnText.textContent = "Classifying...";

    try {
      const payload = {
        domain: rawDomain,
        subdomain: subdomainInput.value.trim() || null,
        app_name: appNameInput.value.trim() || null,
      };

      const res = await fetch("/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Classification failed");
      }

      const data = await res.json();
      renderClassificationResult(data);
    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      btnSubmit.disabled = false;
      btnSpinner.style.display = "none";
      btnText.textContent = "Classify Domain";
    }
  });
}

function renderClassificationResult(data) {
  const placeholder = document.getElementById("result-placeholder");
  const container = document.getElementById("result-container");
  const statusBadge = document.getElementById("result-status-badge");

  placeholder.style.display = "none";
  container.classList.add("show");

  // Status Badge
  statusBadge.style.display = "inline-flex";
  statusBadge.textContent = data.status || "CLASSIFIED";

  // Category & Color
  const catName = data.category || "Miscellaneous";
  const catId = data.category_id || 11;
  const catColor = CATEGORY_COLORS[catName] || "#64748b";
  
  const heroBlock = document.getElementById("result-hero");
  heroBlock.style.setProperty("--category-color", catColor);

  document.getElementById("res-category-name").textContent = catName;
  document.getElementById("res-category-name").style.color = catColor;
  document.getElementById("res-cat-id").textContent = `Category ID: #${catId}`;
  document.getElementById("res-domain-name").querySelector("span").textContent = data.domain;

  // Source Pill
  const sourcePill = document.getElementById("res-source");
  sourcePill.className = `source-pill source-${data.source}`;
  sourcePill.textContent = formatSourceName(data.source);

  // Confidence
  const confPct = Math.round(data.confidence * 100);
  document.getElementById("res-confidence-text").textContent = `${data.confidence.toFixed(2)} (${confPct}%)`;
  document.getElementById("res-confidence-bar").style.width = `${confPct}%`;

  // Metadata boxes
  document.getElementById("res-rule-applied").textContent = data.rule_applied || (data.source === "brand_override" ? "F1 / Brand Override" : "Rule Engine");
  let enrichText = "No (Bypassed / Cached)";
  if (data.enrichment_used) {
    if (data.metadata_fetch_status === "SUCCESS") {
      enrichText = "Success (Data Fetched)";
    } else if (data.metadata_fetch_status) {
      enrichText = `Failed (${data.metadata_fetch_status.replace(/_/g, ' ')})`;
    } else {
      enrichText = "Attempted (No Data)";
    }
  }
  document.getElementById("res-enrichment-used").textContent = enrichText;
  document.getElementById("res-subdomain-split").textContent = data.subdomain ? `${data.subdomain} (TB6 Subdomain)` : "Root Domain";

  // Reason
  document.getElementById("res-reason").textContent = data.reason || "Classified via hierarchical pipeline rules.";

  // Evidence Details
  const evidenceAccordion = document.getElementById("evidence-accordion");
  const evidenceBody = document.getElementById("evidence-content-body");
  if (data.evidence_summary) {
    evidenceAccordion.style.display = "block";
    evidenceBody.innerHTML = `
      <div><strong>Page Title:</strong> ${data.evidence_summary.title || "N/A"}</div>
      <div><strong>Headings:</strong> ${data.evidence_summary.headings ? data.evidence_summary.headings.join(" | ") : "N/A"}</div>
      <div><strong>HTTP Status:</strong> ${data.evidence_summary.http_status || "N/A"}</div>
      <div><strong>JS Heavy:</strong> ${data.evidence_summary.is_js_heavy ? "Yes (SPA framework detected)" : "No"}</div>
      ${data.evidence_summary.fetch_error ? `<div style="color:#ef4444;"><strong>Fetch Note:</strong> ${data.evidence_summary.fetch_error}</div>` : ""}
    `;
  } else {
    evidenceAccordion.style.display = "none";
  }
}

function formatSourceName(src) {
  if (!src) return "Unknown";
  const map = {
    "database": "Database Cache",
    "brand_override": "Brand Override",
    "llm_categorizer": "AI Categorizer (Layer 2)",
    "llm_domain_only": "Domain LLM",
    "llm_enriched": "Enriched LLM",
    "human_override": "Human Override (Protected)",
  };
  return map[src] || src;
}

// 4. Batch Tester
function initBatch() {
  const btn = document.getElementById("btn-run-batch");
  const textarea = document.getElementById("batch-input");
  const spinner = document.getElementById("batch-spinner");
  const tableBody = document.getElementById("batch-table-body");
  const summaryBox = document.getElementById("batch-summary-box");
  const metricsText = document.getElementById("batch-metrics-text");

  btn.addEventListener("click", async () => {
    const lines = textarea.value.split("\n").map(l => l.trim()).filter(Boolean);
    if (!lines.length) {
      alert("Please enter at least one domain.");
      return;
    }

    btn.disabled = true;
    spinner.style.display = "inline-block";

    try {
      const res = await fetch("/classify/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domains: lines }),
      });

      if (!res.ok) throw new Error("Batch processing failed");
      const results = await res.json();

      // Render table
      tableBody.innerHTML = "";
      results.forEach((item, idx) => {
        const tr = document.createElement("tr");
        const color = CATEGORY_COLORS[item.category] || "#9ca3af";
        tr.innerHTML = `
          <td>${idx + 1}</td>
          <td><strong>${item.domain}</strong></td>
          <td>${item.subdomain || "—"}</td>
          <td><span style="color: ${color}; font-weight: 700;">${item.category || "Miscellaneous"}</span></td>
          <td>${item.category_id || 11}</td>
          <td>${item.confidence ? item.confidence.toFixed(2) : "0.00"}</td>
          <td><span class="source-pill source-${item.source}">${formatSourceName(item.source)}</span></td>
          <td><span class="status-badge" style="font-size:0.7rem;">${item.status}</span></td>
        `;
        tableBody.appendChild(tr);
      });

      // Metrics
      const uniqueFqdns = new Set(results.map(r => r.domain)).size;
      summaryBox.style.display = "block";
      metricsText.innerHTML = `
        Total Rows: <strong>${lines.length}</strong> | 
        Unique Domains Deduplicated: <strong>${uniqueFqdns}</strong> | 
        Completed: <strong>${results.length} results mapped</strong>
      `;

    } catch (err) {
      alert("Error: " + err.message);
    } finally {
      btn.disabled = false;
      spinner.style.display = "none";
    }
  });
}

// 5. Load 10 Categories
async function loadCategories() {
  const container = document.getElementById("categories-grid-container");
  const select = document.getElementById("override-category");
  try {
    const res = await fetch("/categories");
    if (!res.ok) return;
    const categories = await res.json();

    container.innerHTML = "";
    categories.forEach(cat => {
      const color = CATEGORY_COLORS[cat.name] || "#6366f1";
      
      // Populate grid card
      const card = document.createElement("div");
      card.className = "category-card";
      card.style.borderTop = `3px solid ${color}`;
      card.innerHTML = `
        <div class="category-card-top">
          <div class="category-card-title" style="color: ${color};">${cat.name}</div>
          <span class="category-card-id">ID #${cat.id}</span>
        </div>
        <div class="category-card-desc">${cat.description}</div>
        <div class="category-card-examples"><strong>Scope:</strong> ${cat.examples}</div>
      `;
      container.appendChild(card);

      // Populate override dropdown
      if (select) {
        const opt = document.createElement("option");
        opt.value = cat.name;
        opt.textContent = `#${cat.id} - ${cat.name}`;
        select.appendChild(opt);
      }
    });
  } catch (e) {
    console.error("Failed to load categories:", e);
  }
}

// 6. Load Locked Rules
async function loadRules() {
  const container = document.getElementById("rules-list-container");
  try {
    const res = await fetch("/rules");
    if (!res.ok) return;
    const data = await res.json();

    container.innerHTML = "";
    data.locked_rules.forEach(rule => {
      const item = document.createElement("div");
      item.className = "rule-item";
      item.innerHTML = `
        <div class="rule-item-header">
          <div>
            <span class="rule-id-badge">${rule.rule_id}</span>
            <span class="rule-title">${rule.name}</span>
          </div>
          <span style="font-size: 0.75rem; color: var(--text-muted);">Scope: ${rule.scope} | Precedence: ${rule.precedence}</span>
        </div>
        <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.4rem;">${rule.description}</div>
        <div class="rule-instruction"><strong>Prompt Injection:</strong> "${rule.instruction}"</div>
      `;
      container.appendChild(item);
    });
  } catch (e) {
    console.error("Failed to load rules:", e);
  }
}

// 7. Human Override Handler
function initHumanOverride() {
  const form = document.getElementById("override-form");
  const alertBox = document.getElementById("override-alert");
  const spinner = document.getElementById("override-spinner");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const domain = document.getElementById("override-domain").value.trim();
    const category = document.getElementById("override-category").value;
    const reason = document.getElementById("override-reason").value.trim();

    if (!domain || !category) return;
    spinner.style.display = "inline-block";

    try {
      const url = `/override/human?domain=${encodeURIComponent(domain)}&category=${encodeURIComponent(category)}&reason=${encodeURIComponent(reason)}`;
      const res = await fetch(url, { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to set human override");
      }
      const data = await res.json();
      
      alertBox.style.display = "block";
      alertBox.style.background = "rgba(16, 185, 129, 0.15)";
      alertBox.style.border = "1px solid rgba(16, 185, 129, 0.3)";
      alertBox.style.color = "#34d399";
      alertBox.innerHTML = `✅ Successfully created protected human override for <strong>${data.domain}</strong> &rarr; <strong>${data.category}</strong>. This record cannot be overwritten by AI.`;
      form.reset();
    } catch (err) {
      alertBox.style.display = "block";
      alertBox.style.background = "rgba(239, 68, 68, 0.15)";
      alertBox.style.border = "1px solid rgba(239, 68, 68, 0.3)";
      alertBox.style.color = "#f87171";
      alertBox.textContent = "Error: " + err.message;
    } finally {
      spinner.style.display = "none";
    }
  });
}

// 8. Database Records View
function initDatabaseView() {
  const tableBody = document.getElementById("db-table-body");
  const searchInput = document.getElementById("db-search-input");
  const refreshBtn = document.getElementById("btn-refresh-db");
  const totalCount = document.getElementById("db-total-count");
  const dbTabBtn = document.getElementById("tab-btn-database");

  let debounceTimer = null;

  async function deleteRecord(domain) {
    if (!confirm(`Are you sure you want to delete '${domain}' from the database?`)) return;
    try {
      const res = await fetch(`/database/records/${encodeURIComponent(domain)}`, { method: "DELETE" });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to delete record");
      }
      fetchAndRenderRecords(searchInput ? searchInput.value.trim() : "");
    } catch (e) {
      alert(`Error deleting record: ${e.message}`);
    }
  }

  async function fetchAndRenderRecords(searchTerm = "") {
    tableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Loading records...</td></tr>`;
    try {
      const url = `/database/records?limit=150${searchTerm ? `&search=${encodeURIComponent(searchTerm)}` : ""}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to fetch database records");
      const data = await res.json();

      if (!data.records || !data.records.length) {
        tableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 2rem;">No matching database records found.</td></tr>`;
        totalCount.textContent = `Total Records: 0`;
        return;
      }

      tableBody.innerHTML = "";
      data.records.forEach((r, idx) => {
        const tr = document.createElement("tr");
        const color = CATEGORY_COLORS[r.category] || "#9ca3af";
        tr.innerHTML = `
          <td><strong>#${idx + 1}</strong></td>
          <td><strong style="color: var(--text-primary);">${r.domain}</strong></td>
          <td>${r.subdomain || "—"}</td>
          <td><span style="color: ${color}; font-weight: 700;">${r.category || "UNKNOWN"}</span></td>
          <td>${r.confidence ? r.confidence.toFixed(2) : "0.00"}</td>
          <td><span class="source-pill source-${r.source}">${formatSourceName(r.source)}</span></td>
          <td><code>${r.rule_applied || "—"}</code></td>
          <td><span class="status-badge" style="font-size:0.7rem;">${r.status}</span></td>
          <td style="max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${r.reason || ''}">${r.reason || '—'}</td>
          <td>
            <button class="pill-btn btn-delete-row" data-domain="${r.domain}" style="padding: 0.25rem 0.6rem; font-size: 0.75rem; color: #f87171; border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.1);">
              🗑️ Delete
            </button>
          </td>
        `;
        const btnDelete = tr.querySelector(".btn-delete-row");
        if (btnDelete) {
          btnDelete.addEventListener("click", () => deleteRecord(r.domain));
        }
        tableBody.appendChild(tr);
      });

      totalCount.innerHTML = `Showing <strong>${data.records.length}</strong> of <strong>${data.total}</strong> stored domain records in database.`;
    } catch (e) {
      tableBody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: #f87171; padding: 1.5rem;">Error loading records: ${e.message}</td></tr>`;
    }
  }

  if (dbTabBtn) {
    dbTabBtn.addEventListener("click", () => fetchAndRenderRecords(searchInput ? searchInput.value.trim() : ""));
  }
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => fetchAndRenderRecords(searchInput ? searchInput.value.trim() : ""));
  }
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        fetchAndRenderRecords(searchInput.value.trim());
      }, 300);
    });
  }

  // Preload initial records
  fetchAndRenderRecords();
}


