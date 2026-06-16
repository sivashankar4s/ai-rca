/**
 * AI Root Cause Analyzer — US1 frontend.
 * Step 1: Fetch failed records for a time window + optional component filter.
 * Supports pagination with cross-page selection keyed by file_trace_id.
 */

'use strict';

// ── State ──────────────────────────────────────────────────────────────────
const selectedIds = new Set();   // file_trace_id values selected across all pages
let allRecords    = [];          // full result from last fetch
let currentPage   = 1;
let pageSize      = 10;

// ── DOM refs ───────────────────────────────────────────────────────────────
const timeRangeEl       = document.getElementById('time-range');
const customDatesEl     = document.getElementById('custom-dates');
const startDtEl         = document.getElementById('start-dt');
const endDtEl           = document.getElementById('end-dt');
const componentEl       = document.getElementById('component');
const fetchBtn          = document.getElementById('fetch-btn');
const fetchSpinner      = document.getElementById('fetch-spinner');
const errorBanner       = document.getElementById('error-banner');
const selectionBar      = document.getElementById('selection-bar');
const selectionCount    = document.getElementById('selection-count');
const clearSelectionBtn = document.getElementById('clear-selection-btn');
const resultsHeader     = document.getElementById('results-header');
const resultsSummary    = document.getElementById('results-summary');
const pageSizeEl        = document.getElementById('page-size');
const tableArea         = document.getElementById('table-area');
const paginationEl      = document.getElementById('pagination');

// ── Helpers ────────────────────────────────────────────────────────────────
function fmt(value) {
  if (value == null || value === '') return '<span style="color:var(--muted)">—</span>';
  return String(value).replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function fmtTs(value) {
  if (!value) return '<span style="color:var(--muted)">—</span>';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return fmt(value);
  }
}

function totalPages() {
  return Math.max(1, Math.ceil(allRecords.length / pageSize));
}

function pageRecords() {
  const start = (currentPage - 1) * pageSize;
  return allRecords.slice(start, start + pageSize);
}

// ── Render ─────────────────────────────────────────────────────────────────
function renderTable() {
  const records = pageRecords();

  if (allRecords.length === 0) {
    tableArea.innerHTML = `
      <div class="empty-state" role="status">
        <strong>No failures found</strong>
        <p>Try a wider time range or remove the component filter.</p>
      </div>`;
    paginationEl.style.display = 'none';
    updateSelectionBar();
    return;
  }

  const allPageSelected = records.length > 0 && records.every(r => selectedIds.has(r.file_trace_id));

  const rows = records.map(r => {
    const checked = selectedIds.has(r.file_trace_id) ? 'checked' : '';
    const traceId = (r.file_trace_id ?? '').replace(/"/g, '&quot;');
    return `
      <tr>
        <td><input type="checkbox" class="row-check" data-id="${traceId}" ${checked} aria-label="Select record ${traceId}"/></td>
        <td>${fmt(r.file_trace_id)}</td>
        <td><span class="tag tag-component">${fmt(r.component_name)}</span></td>
        <td>${fmt(r.application_name)}</td>
        <td>${fmt(r.organization)}</td>
        <td><span class="tag tag-failed">${fmt(r.status)}</span></td>
        <td>${fmt(r.error_code)}</td>
        <td>${fmt(r.stage)}</td>
        <td>${fmtTs(r.event_created_ts)}</td>
      </tr>`;
  }).join('');

  tableArea.innerHTML = `
    <div class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th><input type="checkbox" id="select-all" ${allPageSelected ? 'checked' : ''} aria-label="Select all on page"/></th>
            <th>Trace ID</th>
            <th>Component</th>
            <th>Application</th>
            <th>Org</th>
            <th>Status</th>
            <th>Error Code</th>
            <th>Stage</th>
            <th>Event Time</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;

  // select-all checkbox for this page
  document.getElementById('select-all').addEventListener('change', onSelectAll);

  // individual row checkboxes
  tableArea.querySelectorAll('.row-check').forEach(cb => {
    cb.addEventListener('change', onRowCheck);
  });

  renderPagination();
  updateSelectionBar();
}

function renderPagination() {
  const total = totalPages();
  if (total <= 1) {
    paginationEl.style.display = 'none';
    return;
  }
  paginationEl.style.display = 'flex';

  const buttons = [];
  buttons.push(`<button class="page-btn" id="pg-prev" ${currentPage === 1 ? 'disabled' : ''}>&#8592; Prev</button>`);
  buttons.push(`<span class="page-info">Page ${currentPage} of ${total}</span>`);
  buttons.push(`<button class="page-btn" id="pg-next" ${currentPage === total ? 'disabled' : ''}>Next &#8594;</button>`);

  paginationEl.innerHTML = buttons.join('');
  document.getElementById('pg-prev').addEventListener('click', () => goToPage(currentPage - 1));
  document.getElementById('pg-next').addEventListener('click', () => goToPage(currentPage + 1));
}

function updateResultsHeader() {
  if (allRecords.length === 0) {
    resultsHeader.style.display = 'none';
    return;
  }
  resultsHeader.style.display = 'flex';
  resultsSummary.innerHTML = `Showing <strong>${allRecords.length}</strong> failed record${allRecords.length !== 1 ? 's' : ''}`;
}

function updateSelectionBar() {
  const count = selectedIds.size;
  if (count === 0) {
    selectionBar.classList.remove('visible');
  } else {
    selectionBar.classList.add('visible');
    selectionCount.textContent = `${count} record${count !== 1 ? 's' : ''} selected`;
  }
}

// ── Event handlers ─────────────────────────────────────────────────────────
function onSelectAll(e) {
  const records = pageRecords();
  records.forEach(r => {
    if (r.file_trace_id != null) {
      if (e.target.checked) {
        selectedIds.add(r.file_trace_id);
      } else {
        selectedIds.delete(r.file_trace_id);
      }
    }
  });
  renderTable();
}

function onRowCheck(e) {
  const id = e.target.dataset.id;
  if (id) {
    if (e.target.checked) {
      selectedIds.add(id);
    } else {
      selectedIds.delete(id);
    }
  }
  updateSelectionBar();

  // Update select-all state
  const selectAll = document.getElementById('select-all');
  if (selectAll) {
    const records = pageRecords();
    selectAll.checked = records.length > 0 && records.every(r => selectedIds.has(r.file_trace_id));
  }
}

function goToPage(page) {
  const total = totalPages();
  if (page < 1 || page > total) return;
  currentPage = page;
  renderTable();
}

function showError(msg) {
  errorBanner.textContent = msg;
  errorBanner.style.display = 'block';
}

function clearError() {
  errorBanner.style.display = 'none';
  errorBanner.textContent = '';
}

function setLoading(loading) {
  fetchBtn.disabled = loading;
  fetchSpinner.style.display = loading ? 'inline-block' : 'none';
}

// ── Fetch ──────────────────────────────────────────────────────────────────
async function fetchFailures() {
  clearError();
  setLoading(true);

  const range = timeRangeEl.value;
  const component = componentEl.value.trim() || null;

  const body = { time_range: range, component };

  if (range === 'custom') {
    const start = startDtEl.value;
    const end   = endDtEl.value;
    if (!start || !end) {
      showError('Please provide both start and end dates for a custom range.');
      setLoading(false);
      return;
    }
    body.start = new Date(start).toISOString();
    body.end   = new Date(end).toISOString();
  }

  try {
    const resp = await fetch('/api/failures', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!resp.ok) {
      const detail = await resp.json().catch(() => ({}));
      throw new Error(detail.detail ?? `Server error ${resp.status}`);
    }

    const data = await resp.json();
    allRecords  = data.records ?? [];
    currentPage = 1;

    updateResultsHeader();
    renderTable();
  } catch (err) {
    showError(`Failed to fetch failures: ${err.message}`);
    allRecords = [];
    tableArea.innerHTML = '';
    paginationEl.style.display = 'none';
    resultsHeader.style.display = 'none';
  } finally {
    setLoading(false);
  }
}

// ── Wire up events ─────────────────────────────────────────────────────────
timeRangeEl.addEventListener('change', () => {
  customDatesEl.classList.toggle('visible', timeRangeEl.value === 'custom');
});

fetchBtn.addEventListener('click', fetchFailures);

pageSizeEl.addEventListener('change', () => {
  pageSize = Number(pageSizeEl.value);
  currentPage = 1;
  renderTable();
});

clearSelectionBtn.addEventListener('click', () => {
  selectedIds.clear();
  renderTable();
});
