const API_BASE = "";   // same origin; change to "http://localhost:8000" if running separately

// ── State ────────────────────────────────────────────────────────────────────
let selectedRange    = "1h";
let failureOnly      = true;   // mirrors the Status Filter radio buttons
let allRecords       = [];   // all records from /api/failures
let selectedIndices  = new Set();   // absolute indices into allRecords

// ── DOM refs ─────────────────────────────────────────────────────────────────
const analyzeBtn          = document.getElementById("analyze-btn");
const btnText             = document.getElementById("btn-text");
const btnSpinner          = document.getElementById("btn-spinner");
const componentInput      = document.getElementById("component-input");
const statusBadge         = document.getElementById("status-badge");
const errorBanner         = document.getElementById("error-banner");
const dateFrom            = document.getElementById("date-from");
const dateTo              = document.getElementById("date-to");
const dataSourceSelect    = document.getElementById("data-source-select");
const logBackendSelect    = document.getElementById("log-backend-select");

// Step 1 — failures table
const failuresSection     = document.getElementById("failures-section");
const failuresCountBadge  = document.getElementById("failures-count-badge");
const failuresTbody       = document.getElementById("failures-tbody");
const selectAllCb         = document.getElementById("select-all-cb");
const selectionCount      = document.getElementById("selection-count");
const rcaBtn              = document.getElementById("rca-btn");
const rcaBtnText          = document.getElementById("rca-btn-text");
const rcaSpinner          = document.getElementById("rca-spinner");

// Step 2 — RCA results
const resultsSection      = document.getElementById("results");
const emptyState          = document.getElementById("empty-state");
const summaryText         = document.getElementById("summary-text");
const analyzedAt          = document.getElementById("analyzed-at");
const statTotal           = document.getElementById("stat-total");
const statGroups          = document.getElementById("stat-groups");
const statRange           = document.getElementById("stat-range");
const groupsContainer     = document.getElementById("groups-container");
const codeAnalysisCard    = document.getElementById("code-analysis-card");
const codeAnalysisMeta    = document.getElementById("code-analysis-meta");
const codeAnalysisList    = document.getElementById("code-analysis-list");

// ── Date picker helpers ───────────────────────────────────────────────────────
/** Return a datetime-local string ("YYYY-MM-DDTHH:MM") for a given Date object. */
function toDatetimeLocal(d) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
         `T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Fill the date pickers based on a quick-range string. */
function applyQuickRange(range) {
  const now   = new Date();
  const delta = { "1h": 3600000, "1d": 86400000, "1w": 7 * 86400000 }[range] || 3600000;
  const start = new Date(now.getTime() - delta);
  dateFrom.value = toDatetimeLocal(start);
  dateTo.value   = toDatetimeLocal(now);
}

/** Return { start_date, end_date } from the pickers, or null if either is empty. */
function getDateRange() {
  const s = dateFrom.value;
  const e = dateTo.value;
  return s && e ? { start_date: s, end_date: e } : null;
}

// Auto-fill date pickers on page load with the default quick range (1h)
applyQuickRange(selectedRange);

// ── Providers (data source / log backend) ──────────────────────────────────────
async function loadProviders() {
  try {
    const resp = await fetch(`${API_BASE}/api/providers`);
    if (!resp.ok) return;
    const data = await resp.json();

    populateProviderSelect(dataSourceSelect, data.data_sources, data.defaults.data_source);
    populateProviderSelect(logBackendSelect, data.log_backends, data.defaults.log_backend);
  } catch (e) {
    console.error("Failed to load providers:", e);
  }
}

function populateProviderSelect(select, options, defaultId) {
  select.innerHTML = "";
  (options || []).forEach((opt) => {
    const el = document.createElement("option");
    el.value = opt.id;
    el.textContent = opt.label;
    if (opt.id === defaultId) el.selected = true;
    select.appendChild(el);
  });
}

loadProviders();

// ── Time-range buttons ────────────────────────────────────────────────────────
document.getElementById("time-range-group").addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-range");
  if (!btn) return;
  document.querySelectorAll(".btn-range").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  selectedRange = btn.dataset.range;
  applyQuickRange(selectedRange);
});

// When the user edits a date picker manually, deselect the quick range buttons.
// Keep selectedRange at its last valid enum value ("1h"/"1d"/"1w") — the backend
// will use the explicit start_date/end_date instead whenever they are present.
[dateFrom, dateTo].forEach((el) => {
  el.addEventListener("change", () => {
    document.querySelectorAll(".btn-range").forEach((b) => b.classList.remove("active"));
    // do NOT set selectedRange to "custom" — keep the last enum-valid value
  });
});

// ── Status-filter buttons ─────────────────────────────────────────────────────
document.getElementById("status-filter-group").addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-range");
  if (!btn) return;
  document.querySelectorAll("#status-filter-group .btn-range").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  failureOnly = btn.dataset.failureOnly === "true";
});

// ── Step 1: Fetch Failures ────────────────────────────────────────────────────
analyzeBtn.addEventListener("click", fetchFailures);

async function fetchFailures() {
  setLoading(true);
  hideError();
  hideFailuresTable();
  hideResults();

  try {
    const body = { time_range: selectedRange, failure_only: failureOnly };
    const dates = getDateRange();
    if (dates) {
      body.start_date = dates.start_date;
      body.end_date   = dates.end_date;
    }
    const component = componentInput.value.trim();
    if (component) body.component = component;
    if (dataSourceSelect.value) body.data_source = dataSourceSelect.value;

    const response = await fetch(`${API_BASE}/api/failures`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    allRecords = data.records || [];

    if (allRecords.length === 0) {
      emptyState.classList.remove("hidden");
      setStatus("done");
      return;
    }

    renderFailuresTable(allRecords);
    setStatus("done");
  } catch (err) {
    showError(err.message);
    setStatus("error");
  } finally {
    setLoading(false);
  }
}

// ── Step 2: Find RCA ──────────────────────────────────────────────────────────
rcaBtn.addEventListener("click", runRCA);

async function runRCA() {
  const selected = getSelectedRecords();
  if (selected.length === 0) return;

  setRCALoading(true);
  hideError();
  hideResults();

  try {
    const dates = getDateRange();
    const body = {
      time_range: selectedRange,
      records: selected,
    };
    if (dates) {
      body.start_date = dates.start_date;
      body.end_date   = dates.end_date;
    }
    if (logBackendSelect.value) body.log_backend = logBackendSelect.value;

    const response = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    renderResults(data);
    setStatus("done");
  } catch (err) {
    showError(err.message);
    setStatus("error");
  } finally {
    setRCALoading(false);
  }
}

// ── Pagination state ──────────────────────────────────────────────────────────
let currentPage = 1;
let pageSize    = 10;

const pageSizeSelect  = document.getElementById("page-size-select");
const paginationInfo  = document.getElementById("pagination-info");
const pgFirst         = document.getElementById("pg-first");
const pgPrev          = document.getElementById("pg-prev");
const pgNext          = document.getElementById("pg-next");
const pgLast          = document.getElementById("pg-last");

pageSizeSelect.addEventListener("change", () => {
  pageSize    = parseInt(pageSizeSelect.value, 10);
  currentPage = 1;
  renderPage();
});
pgFirst.addEventListener("click", () => { currentPage = 1;                          renderPage(); });
pgPrev .addEventListener("click", () => { if (currentPage > 1) currentPage--;       renderPage(); });
pgNext .addEventListener("click", () => { if (currentPage < totalPages()) currentPage++; renderPage(); });
pgLast .addEventListener("click", () => { currentPage = totalPages();               renderPage(); });

function totalPages() {
  return Math.max(1, Math.ceil(allRecords.length / pageSize));
}

// ── Failures table ────────────────────────────────────────────────────────────
function renderFailuresTable(records) {
  // records is already stored in allRecords by fetchFailures
  currentPage = 1;
  failuresCountBadge.textContent = `${records.length} record${records.length !== 1 ? "s" : ""}`;
  failuresCountBadge.className   = "badge badge--done";
  document.getElementById("records-section-title").textContent =
    failureOnly ? "Failure Records" : "All Records";
  failuresSection.classList.remove("hidden");
  selectAllCb.checked       = false;
  selectAllCb.indeterminate = false;
  renderPage();
}

function renderPage() {
  failuresTbody.innerHTML = "";

  const total  = allRecords.length;
  const pages  = totalPages();
  if (currentPage > pages) currentPage = pages;

  const start  = (currentPage - 1) * pageSize;          // 0-based index into allRecords
  const end    = Math.min(start + pageSize, total);
  const slice  = allRecords.slice(start, end);

  // Update pagination info
  paginationInfo.textContent = total === 0
    ? "No records"
    : `${start + 1}–${end} of ${total}`;

  pgFirst.disabled = currentPage === 1;
  pgPrev .disabled = currentPage === 1;
  pgNext .disabled = currentPage === pages;
  pgLast .disabled = currentPage === pages;

  slice.forEach((r, sliceIdx) => {
    const absIdx = start + sliceIdx;          // index into allRecords for selection tracking
    const ed  = r.event_data || {};
    const tr  = document.createElement("tr");
    tr.dataset.idx = absIdx;
    tr.innerHTML = `
      <td class="cb-col"><input type="checkbox" class="row-cb" data-idx="${absIdx}" /></td>
      <td title="${escHtml(r.component_name)}">${escHtml(r.component_name || "-")}</td>
      <td>${escHtml(r.custom_key2 || "-")}</td>
      <td class="mono" title="${escHtml(r.custom_key1)}">${escHtml(shortId(r.custom_key1))}</td>
      <td class="mono" title="${escHtml(r.custom_key3)}">${escHtml(shortId(r.custom_key3))}</td>
      <td>${escHtml(r.event_created_timestamp || "-")}</td>
      <td>${escHtml(ed.error_code || "-")}</td>
      <td><span class="status-pill">${escHtml(r.status)}</span></td>`;

    // Restore checked state if this record was already selected
    const cb = tr.querySelector(".row-cb");
    if (selectedIndices.has(absIdx)) {
      cb.checked = true;
      tr.classList.add("row-selected");
    }

    cb.addEventListener("change", onRowCheckboxChange);
    tr.addEventListener("click", (e) => {
      if (e.target.type === "checkbox") return;
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event("change"));
    });
    failuresTbody.appendChild(tr);
  });

  updateSelectionBar();
  updateSelectAllState();
}

// Select-all toggle — applies to ALL records (not just current page)
selectAllCb.addEventListener("change", () => {
  if (selectAllCb.checked) {
    allRecords.forEach((_, i) => selectedIndices.add(i));
  } else {
    selectedIndices.clear();
  }
  renderPage();   // re-render current page to reflect state
});

function onRowCheckboxChange(e) {
  const cb  = e.target;
  const idx = parseInt(cb.dataset.idx, 10);
  const tr  = cb.closest("tr");
  if (cb.checked) {
    selectedIndices.add(idx);
  } else {
    selectedIndices.delete(idx);
  }
  tr.classList.toggle("row-selected", cb.checked);
  updateSelectionBar();
  updateSelectAllState();
}

function updateSelectAllState() {
  const total   = allRecords.length;
  const checked = selectedIndices.size;
  selectAllCb.indeterminate = checked > 0 && checked < total;
  selectAllCb.checked       = total > 0 && checked === total;
}

function updateSelectionBar() {
  const n = selectedIndices.size;
  selectionCount.textContent = `${n} of ${allRecords.length} selected`;
  rcaBtn.disabled = n === 0;
}

function getSelectedRecords() {
  return [...selectedIndices].sort((a, b) => a - b).map((i) => allRecords[i]);
}

// ── RCA Results render ────────────────────────────────────────────────────────
function renderResults(data) {
  if (data.total_failures === 0) {
    emptyState.classList.remove("hidden");
    return;
  }

  summaryText.textContent = data.summary;
  analyzedAt.textContent  = formatDate(data.analyzed_at);
  statTotal.textContent   = data.total_failures;
  statGroups.textContent  = data.failure_groups.length;
  statRange.textContent   = rangeLabel(data.time_range);

  groupsContainer.innerHTML = "";
  data.failure_groups.forEach((group) => {
    groupsContainer.appendChild(buildGroupCard(group));
  });

  renderCodeAnalysis(data.code_analysis);

  resultsSection.classList.remove("hidden");
  resultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCodeAnalysis(codeAnalysis) {
  codeAnalysisList.innerHTML = "";

  if (!codeAnalysis) {
    codeAnalysisCard.classList.add("hidden");
    return;
  }

  codeAnalysisCard.classList.remove("hidden");
  codeAnalysisMeta.textContent = `Repository: ${codeAnalysis.repo}`;

  if (codeAnalysis.error) {
    codeAnalysisList.innerHTML = `<p class="code-analysis-error">${escHtml(codeAnalysis.error)}</p>`;
    return;
  }

  if (!codeAnalysis.items || codeAnalysis.items.length === 0) {
    codeAnalysisList.innerHTML = `<p class="code-analysis-empty">No recent commits or pull requests found in this time window.</p>`;
    return;
  }

  codeAnalysis.items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "code-analysis-item";

    const badge = document.createElement("span");
    badge.className = `code-analysis-badge code-analysis-badge--${item.type}`;
    badge.textContent = item.type === "pull_request" ? "PR" : "Commit";

    const title = document.createElement(item.url ? "a" : "span");
    title.className = "code-analysis-title";
    title.textContent = item.title || "(no title)";
    if (item.url) {
      title.href = item.url;
      title.target = "_blank";
      title.rel = "noopener noreferrer";
    }

    const meta = document.createElement("span");
    meta.className = "code-analysis-item-meta";
    const parts = [];
    if (item.author) parts.push(item.author);
    if (item.date) parts.push(formatDate(item.date));
    meta.textContent = parts.join(" · ");

    row.appendChild(badge);
    row.appendChild(title);
    row.appendChild(meta);
    codeAnalysisList.appendChild(row);
  });
}

function buildGroupCard(group) {
  const card = document.createElement("div");
  card.className = "group-card";

  const catClass = `cat-${group.failure_category.toLowerCase()}`;

  card.innerHTML = `
    <div class="group-header">
      <div class="group-header-left">
        <span class="group-component">${escHtml(group.component)}</span>
        <span class="category-badge ${catClass}">${escHtml(group.failure_category)}</span>
        <span class="group-pattern">${escHtml(group.error_pattern)}</span>
      </div>
      <div class="group-header-right">
        <span class="impact-pill">&#9888; ${group.impact_count} failure${group.impact_count !== 1 ? "s" : ""}</span>
        <span class="chevron">&#9660;</span>
      </div>
    </div>
    <div class="group-body">
      <div class="group-section">
        <h4>Root Cause</h4>
        <div class="root-cause-text">${escHtml(group.root_cause)}</div>
      </div>
      ${group.immediate_action ? `
      <div class="group-section">
        <h4>⚡ Immediate Action</h4>
        <div class="dev-action-box dev-action--urgent">${escHtml(group.immediate_action)}</div>
      </div>` : ""}
      ${group.likely_fix ? `
      <div class="group-section">
        <h4>🔧 Likely Fix</h4>
        <div class="dev-action-box dev-action--fix">${escHtml(group.likely_fix)}</div>
      </div>` : ""}
      ${group.affected_files && group.affected_files.length ? `
      <div class="group-section">
        <h4>📂 Affected Services / Files</h4>
        <div class="affected-files-list">
          ${group.affected_files.map(f => `<span class="affected-file-chip">${escHtml(f)}</span>`).join("")}
        </div>
      </div>` : ""}
      ${group.escalation_path ? `
      <div class="group-section">
        <h4>📣 Escalation Path</h4>
        <div class="dev-action-box dev-action--escalate">${escHtml(group.escalation_path)}</div>
      </div>` : ""}
      ${group.log_samples && group.log_samples.length ? `
      <div class="group-section">
        <h4>Log Samples</h4>
        <div class="log-block">${group.log_samples.map(escHtml).join("\n")}</div>
      </div>` : ""}
      ${group.cw_log_url ? `
      <div class="group-section cw-link-section">
        <a class="btn-cw-link" href="${escHtml(group.cw_log_url)}" target="_blank" rel="noopener noreferrer">
          &#128269; View Logs in CloudWatch
        </a>
      </div>` : ""}
      ${group.records && group.records.length ? `
      <div class="group-section">
        <h4>Affected Records</h4>
        <table class="records-table">
          <thead>
            <tr>
              <th>File Trace ID</th><th>Component</th><th>Stage</th><th>Error Code</th><th>Created</th>
            </tr>
          </thead>
          <tbody>
            ${group.records.map((r) => {
              const ed = r.event_data || {};
              return `
              <tr>
                <td class="mono" title="${escHtml(r.custom_key1)}">${escHtml(shortId(r.custom_key1))}</td>
                <td>${escHtml(r.component_name || "-")}</td>
                <td>${escHtml(r.custom_key2 || "-")}</td>
                <td>${escHtml(ed.error_code || "-")}</td>
                <td>${escHtml(r.event_created_timestamp || "-")}</td>
              </tr>`;
            }).join("")}
          </tbody>
        </table>
      </div>` : ""}
    </div>`;

  card.querySelector(".group-header").addEventListener("click", () => {
    card.classList.toggle("open");
  });

  return card;
}

// ── UI helpers ────────────────────────────────────────────────────────────────
function setLoading(loading) {
  analyzeBtn.disabled = loading;
  btnText.textContent = loading ? "Fetching..." : "Fetch Failures";
  btnSpinner.classList.toggle("hidden", !loading);
  if (loading) setStatus("running");
}

function setRCALoading(loading) {
  rcaBtn.disabled = loading;
  rcaBtnText.textContent = loading ? "Analysing..." : "Analyze Root Cause";
  rcaSpinner.classList.toggle("hidden", !loading);
  analyzeBtn.disabled = loading;
  if (loading) setStatus("running");
}

function setStatus(state) {
  const labels = { idle: "Idle", running: "Running...", done: "Complete", error: "Error" };
  statusBadge.textContent = labels[state] || state;
  statusBadge.className   = `badge badge--${state}`;
}

function showError(msg) {
  errorBanner.textContent = `Error: ${msg}`;
  errorBanner.classList.remove("hidden");
}

function hideError() { errorBanner.classList.add("hidden"); }

function hideFailuresTable() {
  failuresSection.classList.add("hidden");
  failuresTbody.innerHTML = "";
  allRecords      = [];
  selectedIndices = new Set();
  currentPage     = 1;
  selectAllCb.checked       = false;
  selectAllCb.indeterminate = false;
  updateSelectionBar();
}

function hideResults() {
  resultsSection.classList.add("hidden");
  emptyState.classList.add("hidden");
  groupsContainer.innerHTML = "";
  codeAnalysisCard.classList.add("hidden");
  codeAnalysisList.innerHTML = "";
}

// ── Time-range buttons ────────────────────────────────────────────────────────
document.getElementById("time-range-group").addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-range");
  if (!btn) return;
  document.querySelectorAll(".btn-range").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  selectedRange = btn.dataset.range;
});

// ── Utilities ─────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDate(iso) {
  try { return new Date(iso).toLocaleString(); }
  catch { return iso; }
}

function rangeLabel(range) {
  return { "1h": "1 Hour", "1d": "1 Day", "1w": "1 Week" }[range] || range;
}

function shortId(str) {
  if (!str) return "-";
  return str.length > 12 ? str.slice(0, 8) + "…" : str;
}

// ── Config Panel ──────────────────────────────────────────────────────────────
const cfgOverlay       = document.getElementById("cfg-overlay");
const cfgDrawer        = document.getElementById("cfg-drawer");
const cfgOpenBtn       = document.getElementById("cfg-open-btn");
const cfgCloseBtn      = document.getElementById("cfg-close-btn");
const cfgCancelBtn     = document.getElementById("cfg-cancel-btn");
const cfgSaveBtn       = document.getElementById("cfg-save-btn");
const cfgSaveBanner    = document.getElementById("cfg-save-banner");
const cfgRefreshModels = document.getElementById("cfg-refresh-models");

const cfgKeyId   = document.getElementById("cfg-key-id");
const cfgSecret  = document.getElementById("cfg-secret");
const cfgToken   = document.getElementById("cfg-token");
const cfgRegion  = document.getElementById("cfg-region");
const cfgDb      = document.getElementById("cfg-db");
const cfgTable   = document.getElementById("cfg-table");
const cfgModel   = document.getElementById("cfg-model");
const cfgGrafanaUrl = document.getElementById("cfg-grafana-url");
const cfgGrafanaKey = document.getElementById("cfg-grafana-key");
const cfgGrafanaUid = document.getElementById("cfg-grafana-uid");
const cfgDbUrl      = document.getElementById("cfg-db-url");
const cfgDbStatus   = document.getElementById("cfg-db-status");
const cfgGithubRepo = document.getElementById("cfg-github-repo");
const cfgGithubToken = document.getElementById("cfg-github-token");
const cfgGithubMcpCommand = document.getElementById("cfg-github-mcp-command");
const cfgAnthropicKey = document.getElementById("cfg-anthropic-key");

const cfgSecretHint = document.getElementById("cfg-secret-hint");
const cfgTokenHint  = document.getElementById("cfg-token-hint");
const cfgGrafanaKeyHint = document.getElementById("cfg-grafana-key-hint");
const cfgGithubTokenHint = document.getElementById("cfg-github-token-hint");
const cfgAnthropicKeyHint = document.getElementById("cfg-anthropic-key-hint");

async function openCfgDrawer() {
  cfgDrawer.classList.remove("hidden");
  cfgOverlay.classList.remove("hidden");
  // Load config first so the saved model is known before populating the dropdown
  await loadConfig();
  loadModels();
}

function closeCfgDrawer() {
  cfgDrawer.classList.add("hidden");
  cfgOverlay.classList.add("hidden");
  cfgSaveBanner.classList.add("hidden");
}

cfgOpenBtn.addEventListener("click", openCfgDrawer);
cfgCloseBtn.addEventListener("click", closeCfgDrawer);
cfgCancelBtn.addEventListener("click", closeCfgDrawer);
cfgOverlay.addEventListener("click", closeCfgDrawer);

// Show/hide password toggle
document.querySelectorAll(".cfg-eye-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const inp = document.getElementById(btn.dataset.target);
    if (!inp) return;
    inp.type = inp.type === "password" ? "text" : "password";
  });
});

async function loadConfig() {
  try {
    const resp = await fetch(`${API_BASE}/api/config`);
    if (!resp.ok) return;
    const cfg = await resp.json();
    cfgKeyId.value  = cfg.aws_access_key_id  || "";
    cfgRegion.value = cfg.aws_region         || "";
    cfgDb.value     = cfg.athena_database    || "";
    cfgTable.value  = cfg.athena_table       || "";
    // Secrets: show hint instead of exposing the value
    cfgSecret.value = "";
    cfgToken.value  = "";
    cfgSecretHint.textContent = cfg.aws_secret_access_key_set
      ? "✔ Value set (leave blank to keep)"
      : "⚠ Not set";
    cfgSecretHint.style.color = cfg.aws_secret_access_key_set ? "var(--success)" : "var(--warning)";
    cfgTokenHint.textContent = cfg.aws_session_token_set
      ? "✔ Value set (leave blank to keep)"
      : "⚠ Not set";
    cfgTokenHint.style.color = cfg.aws_session_token_set ? "var(--success)" : "var(--warning)";

    // Grafana / Loki
    cfgGrafanaUrl.value = cfg.grafana_loki_url    || "";
    cfgGrafanaUid.value = cfg.grafana_datasource_uid || "";
    cfgGrafanaKey.value = "";
    cfgGrafanaKeyHint.textContent = cfg.grafana_api_key_set
      ? "✔ Value set (leave blank to keep)"
      : "⚠ Not set";
    cfgGrafanaKeyHint.style.color = cfg.grafana_api_key_set ? "var(--success)" : "var(--warning)";

    // Local Database (Postgres) — read-only status
    cfgDbUrl.textContent = cfg.database_url_masked || "-";
    cfgDbStatus.textContent = cfg.database_connected ? "✔ Connected" : "✖ Not reachable";
    cfgDbStatus.style.color = cfg.database_connected ? "var(--success)" : "var(--danger)";

    // GitHub (Code Analysis Agent)
    cfgGithubRepo.value = cfg.github_repo || "";
    cfgGithubMcpCommand.value = cfg.github_mcp_command || "";
    cfgGithubToken.value = "";
    cfgGithubTokenHint.textContent = cfg.github_token_set
      ? "✔ Value set (leave blank to keep)"
      : "⚠ Not set";
    cfgGithubTokenHint.style.color = cfg.github_token_set ? "var(--success)" : "var(--warning)";

    // Anthropic LLM
    cfgAnthropicKey.value = "";
    cfgAnthropicKeyHint.textContent = cfg.anthropic_api_key_set
      ? "✔ Value set (leave blank to keep)"
      : "⚠ Not set";
    cfgAnthropicKeyHint.style.color = cfg.anthropic_api_key_set ? "var(--success)" : "var(--warning)";

    // Set model after models are loaded
    cfgModel.dataset.currentModel = cfg.llm_model || "";
  } catch (e) {
    console.error("Failed to load config:", e);
  }
}

async function loadModels() {
  cfgRefreshModels.disabled = true;
  cfgModel.innerHTML = '<option value="">Loading…</option>';
  try {
    const resp = await fetch(`${API_BASE}/api/models`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const models  = data.models  || [];
    // Prefer data.current (live from GET /api/models → settings) over the cached dataset attribute
    const current = data.current || cfgModel.dataset.currentModel || "";

    cfgModel.innerHTML = "";

    if (models.length === 0) {
      cfgModel.innerHTML = '<option value="">No models found</option>';
    } else {
      // Always ensure the current model appears even if not in the list
      const allModels = current && !models.includes(current)
        ? [current, ...models]
        : models;

      allModels.forEach((id) => {
        const opt = document.createElement("option");
        opt.value = id;
        // Friendly label: prefer claude-sonnet variants at top
        opt.textContent = id;
        if (id === current) opt.selected = true;
        cfgModel.appendChild(opt);
      });
    }
  } catch (e) {
    cfgModel.innerHTML = `<option value="${escHtml(cfgModel.dataset.currentModel || "")}">${escHtml(cfgModel.dataset.currentModel || "Error loading models")}</option>`;
    console.error("Failed to load models:", e);
  } finally {
    cfgRefreshModels.disabled = false;
  }
}

cfgRefreshModels.addEventListener("click", loadModels);

async function saveConfig() {
  cfgSaveBtn.disabled = true;
  cfgSaveBtn.textContent = "Saving…";
  cfgSaveBanner.classList.add("hidden");

  const body = {};
  if (cfgKeyId.value.trim())   body.aws_access_key_id  = cfgKeyId.value.trim();
  if (cfgSecret.value.trim())  body.aws_secret_access_key = cfgSecret.value.trim();
  if (cfgToken.value.trim())   body.aws_session_token  = cfgToken.value.trim();
  if (cfgRegion.value.trim())  body.aws_region         = cfgRegion.value.trim();
  if (cfgDb.value.trim())      body.athena_database    = cfgDb.value.trim();
  if (cfgTable.value.trim())   body.athena_table       = cfgTable.value.trim();
  if (cfgModel.value)          body.llm_model          = cfgModel.value;
  if (cfgGrafanaUrl.value.trim()) body.grafana_loki_url     = cfgGrafanaUrl.value.trim();
  if (cfgGrafanaKey.value.trim()) body.grafana_api_key      = cfgGrafanaKey.value.trim();
  if (cfgGrafanaUid.value.trim()) body.grafana_datasource_uid = cfgGrafanaUid.value.trim();
  if (cfgGithubRepo.value.trim()) body.github_repo          = cfgGithubRepo.value.trim();
  if (cfgGithubToken.value.trim()) body.github_token        = cfgGithubToken.value.trim();
  if (cfgGithubMcpCommand.value.trim()) body.github_mcp_command = cfgGithubMcpCommand.value.trim();
  if (cfgAnthropicKey.value.trim()) body.anthropic_api_key = cfgAnthropicKey.value.trim();

  try {
    const resp = await fetch(`${API_BASE}/api/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const result = await resp.json();
    const updated = result.updated || [];
    showCfgBanner(
      updated.length
        ? `✔ Saved: ${updated.join(", ")}`
        : "✔ No changes (all fields were blank)",
      "success"
    );
    // Refresh hints after save, then auto-close
    loadConfig();
    setTimeout(closeCfgDrawer, 1500);
  } catch (e) {
    showCfgBanner(`✖ Save failed: ${e.message}`, "error");
  } finally {
    cfgSaveBtn.disabled = false;
    cfgSaveBtn.textContent = "Save & Apply";
  }
}

cfgSaveBtn.addEventListener("click", saveConfig);

function showCfgBanner(msg, type) {
  cfgSaveBanner.textContent = msg;
  cfgSaveBanner.className = `cfg-save-banner cfg-save-banner--${type}`;
  cfgSaveBanner.classList.remove("hidden");
}

// ── Page navigation ─────────────────────────────────────────────────────────────
const rcaPage    = document.getElementById("rca-page");
const sourcePage = document.getElementById("source-page");

document.querySelectorAll(".page-nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".page-nav-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");

    const target = btn.dataset.page;
    rcaPage.classList.toggle("hidden", target !== "rca-page");
    sourcePage.classList.toggle("hidden", target !== "source-page");

    if (target === "source-page") {
      loadGithubPage();
    }
  });
});

// ── Source Code Intelligence ─────────────────────────────────────────────────────
const githubRepoName     = document.getElementById("github-repo-name");
const githubRepoDesc     = document.getElementById("github-repo-desc");
const githubRepoLink     = document.getElementById("github-repo-link");
const githubNotConfigured = document.getElementById("github-not-configured");
const githubError         = document.getElementById("github-error");
const githubBranchesList  = document.getElementById("github-branches-list");
const githubPrsList       = document.getElementById("github-prs-list");
const githubBranchesRefresh = document.getElementById("github-branches-refresh");
const githubPrsRefresh      = document.getElementById("github-prs-refresh");
const githubPrStateGroup    = document.getElementById("github-pr-state-group");
const codeReviewSection      = document.getElementById("code-review-section");
const codeReviewTarget       = document.getElementById("code-review-target");
const codeReviewBody         = document.getElementById("code-review-body");
const codeReviewClose        = document.getElementById("code-review-close");

let githubPrState = "open";
let githubLoaded = false;

function loadGithubPage() {
  loadGithubRepo();
  loadGithubBranches();
  loadGithubPullRequests();
  githubLoaded = true;
}

async function loadGithubRepo() {
  githubError.classList.add("hidden");
  githubNotConfigured.classList.add("hidden");
  try {
    const resp = await fetch(`${API_BASE}/api/github/repo`);
    const data = await resp.json();

    if (!data.configured) {
      githubNotConfigured.classList.remove("hidden");
      githubRepoName.textContent = "-";
      githubRepoDesc.textContent = "";
      githubRepoLink.classList.add("hidden");
      return;
    }

    githubRepoName.textContent = data.repo || "-";
    githubRepoDesc.textContent = data.description || "";

    if (data.url) {
      githubRepoLink.href = data.url;
      githubRepoLink.classList.remove("hidden");
    } else {
      githubRepoLink.classList.add("hidden");
    }

    if (data.error) {
      githubError.textContent = data.error;
      githubError.classList.remove("hidden");
    }
  } catch (e) {
    console.error("Failed to load repo info:", e);
    githubError.textContent = `Failed to load repository info: ${e.message}`;
    githubError.classList.remove("hidden");
  }
}

async function loadGithubBranches() {
  githubBranchesList.innerHTML = `<p class="code-analysis-empty">Loading…</p>`;
  try {
    const resp = await fetch(`${API_BASE}/api/github/branches`);
    const data = await resp.json();

    if (data.error) {
      githubBranchesList.innerHTML = `<p class="code-analysis-error">${escHtml(data.error)}</p>`;
      return;
    }

    if (!data.branches || data.branches.length === 0) {
      githubBranchesList.innerHTML = `<p class="code-analysis-empty">No branches found.</p>`;
      return;
    }

    githubBranchesList.innerHTML = "";
    data.branches.forEach((b) => {
      const row = document.createElement("div");
      row.className = "github-branch-item";

      const name = document.createElement("span");
      name.className = "github-branch-name";
      name.textContent = b.name;
      row.appendChild(name);

      if (b.protected) {
        const badge = document.createElement("span");
        badge.className = "github-protected-badge";
        badge.textContent = "Protected";
        row.appendChild(badge);
      }

      if (b.sha) {
        const sha = document.createElement("span");
        sha.className = "github-branch-sha";
        sha.textContent = b.sha.slice(0, 7);
        row.appendChild(sha);
      }

      const reviewBtn = document.createElement("button");
      reviewBtn.className = "btn-secondary code-review-btn";
      reviewBtn.textContent = "Review";
      reviewBtn.addEventListener("click", () => runCodeReview(`branch ${b.name}`, () =>
        fetch(`${API_BASE}/api/github/branches/review?branch=${encodeURIComponent(b.name)}`)
      ));
      row.appendChild(reviewBtn);

      githubBranchesList.appendChild(row);
    });
  } catch (e) {
    console.error("Failed to load branches:", e);
    githubBranchesList.innerHTML = `<p class="code-analysis-error">Failed to load branches: ${escHtml(e.message)}</p>`;
  }
}

async function loadGithubPullRequests() {
  githubPrsList.innerHTML = `<p class="code-analysis-empty">Loading…</p>`;
  try {
    const resp = await fetch(`${API_BASE}/api/github/pull-requests?state=${githubPrState}`);
    const data = await resp.json();

    if (data.error) {
      githubPrsList.innerHTML = `<p class="code-analysis-error">${escHtml(data.error)}</p>`;
      return;
    }

    if (!data.pull_requests || data.pull_requests.length === 0) {
      githubPrsList.innerHTML = `<p class="code-analysis-empty">No pull requests found.</p>`;
      return;
    }

    githubPrsList.innerHTML = "";
    data.pull_requests.forEach((pr) => {
      const row = document.createElement("div");
      row.className = "github-pr-item";

      const number = document.createElement("span");
      number.className = "github-pr-number";
      number.textContent = `#${pr.number}`;
      row.appendChild(number);

      const title = document.createElement(pr.url ? "a" : "span");
      title.className = "github-pr-title";
      title.textContent = pr.title || "(no title)";
      if (pr.url) {
        title.href = pr.url;
        title.target = "_blank";
        title.rel = "noopener noreferrer";
      }
      row.appendChild(title);

      const state = document.createElement("span");
      state.className = `github-pr-state github-pr-state--${pr.state}`;
      state.textContent = pr.state;
      row.appendChild(state);

      const meta = document.createElement("span");
      meta.className = "github-pr-meta";
      const parts = [];
      if (pr.author) parts.push(pr.author);
      if (pr.branch) parts.push(pr.branch);
      if (pr.updated_at) parts.push(formatDate(pr.updated_at));
      meta.textContent = parts.join(" · ");
      row.appendChild(meta);

      const reviewBtn = document.createElement("button");
      reviewBtn.className = "btn-secondary code-review-btn";
      reviewBtn.textContent = "Review";
      reviewBtn.addEventListener("click", () => runCodeReview(`PR #${pr.number}`, () =>
        fetch(`${API_BASE}/api/github/pull-requests/${pr.number}/review`)
      ));
      row.appendChild(reviewBtn);

      githubPrsList.appendChild(row);
    });
  } catch (e) {
    console.error("Failed to load pull requests:", e);
    githubPrsList.innerHTML = `<p class="code-analysis-error">Failed to load pull requests: ${escHtml(e.message)}</p>`;
  }
}

const CODE_REVIEW_SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

async function runCodeReview(targetLabel, fetchFn) {
  codeReviewSection.classList.remove("hidden");
  codeReviewTarget.textContent = targetLabel;
  codeReviewBody.innerHTML = `<p class="code-analysis-empty">Reviewing ${escHtml(targetLabel)}… this may take a minute.</p>`;
  codeReviewSection.scrollIntoView({ behavior: "smooth", block: "nearest" });

  try {
    const resp = await fetchFn();
    const data = await resp.json();

    if (data.error) {
      codeReviewBody.innerHTML = `<p class="code-analysis-error">${escHtml(data.error)}</p>`;
      return;
    }

    codeReviewBody.innerHTML = "";

    if (data.summary) {
      const summary = document.createElement("p");
      summary.className = "code-review-summary";
      summary.textContent = data.summary;
      codeReviewBody.appendChild(summary);
    }

    const findings = (data.findings || []).slice().sort(
      (a, b) => (CODE_REVIEW_SEVERITY_ORDER[a.severity] ?? 9) - (CODE_REVIEW_SEVERITY_ORDER[b.severity] ?? 9)
    );

    if (findings.length === 0) {
      const empty = document.createElement("p");
      empty.className = "code-analysis-empty";
      empty.textContent = "No issues found.";
      codeReviewBody.appendChild(empty);
      return;
    }

    findings.forEach((f) => {
      const item = document.createElement("div");
      item.className = `code-review-finding code-review-finding--${f.severity || "info"}`;

      const header = document.createElement("div");
      header.className = "code-review-finding-header";

      const severity = document.createElement("span");
      severity.className = `code-review-severity code-review-severity--${f.severity || "info"}`;
      severity.textContent = (f.severity || "info").toUpperCase();
      header.appendChild(severity);

      const category = document.createElement("span");
      category.className = "code-review-category";
      category.textContent = (f.category || "").replace(/_/g, " ");
      header.appendChild(category);

      const title = document.createElement("span");
      title.className = "code-review-title";
      title.textContent = f.title || "";
      header.appendChild(title);

      item.appendChild(header);

      if (f.file) {
        const location = document.createElement("div");
        location.className = "code-review-location";
        location.textContent = f.line ? `${f.file}:${f.line}` : f.file;
        item.appendChild(location);
      }

      if (f.description) {
        const desc = document.createElement("p");
        desc.className = "code-review-description";
        desc.textContent = f.description;
        item.appendChild(desc);
      }

      if (f.recommendation) {
        const rec = document.createElement("p");
        rec.className = "code-review-recommendation";
        rec.innerHTML = `<strong>Recommendation:</strong> ${escHtml(f.recommendation)}`;
        item.appendChild(rec);
      }

      codeReviewBody.appendChild(item);
    });
  } catch (e) {
    console.error("Code review failed:", e);
    codeReviewBody.innerHTML = `<p class="code-analysis-error">Code review failed: ${escHtml(e.message)}</p>`;
  }
}

codeReviewClose.addEventListener("click", () => {
  codeReviewSection.classList.add("hidden");
  codeReviewBody.innerHTML = "";
});

githubBranchesRefresh.addEventListener("click", loadGithubBranches);
githubPrsRefresh.addEventListener("click", loadGithubPullRequests);

githubPrStateGroup.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-range");
  if (!btn) return;
  githubPrStateGroup.querySelectorAll(".btn-range").forEach((b) => b.classList.remove("active"));
  btn.classList.add("active");
  githubPrState = btn.dataset.state;
  loadGithubPullRequests();
});
