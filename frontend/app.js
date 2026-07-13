'use strict';

// ── State ──────────────────────────────────────────────────────────────────
const selectedIds = new Set();   // file_trace_id values selected across all pages
let allRecords    = [];          // full result from last fetch
let currentPage   = 1;
let pageSize      = 10;

// ── DOM refs ───────────────────────────────────────────────────────────────
const timeRangeEl       = document.getElementById('time-range');
const dataSourceEl      = document.getElementById('data-source');
const customDatesEl     = document.getElementById('custom-dates');
const startDtEl         = document.getElementById('start-dt');
const endDtEl           = document.getElementById('end-dt');
const componentEl       = document.getElementById('component');
const traceIdEl         = document.getElementById('trace-id');
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
const analyzePanel      = document.getElementById('analyze-panel');
const analyzeCount      = document.getElementById('analyze-count');
const logBackendEl      = document.getElementById('log-backend');
const analyzeBtn        = document.getElementById('analyze-btn');
const analyzeSpinner    = document.getElementById('analyze-spinner');
const analyzeResult     = document.getElementById('analyze-result');

// ── Providers loading ──────────────────────────────────────────────────────
async function loadProviders() {
  try {
    const resp = await fetch('/api/providers');
    if (!resp.ok) return;
    const data = await resp.json();

    dataSourceEl.innerHTML = '';
    for (const ds of data.data_sources) {
      const opt = document.createElement('option');
      opt.value = ds.id;
      opt.textContent = ds.label;
      if (ds.is_default) opt.selected = true;
      dataSourceEl.appendChild(opt);
    }

    logBackendEl.innerHTML = '';
    for (const lb of data.log_backends) {
      const opt = document.createElement('option');
      opt.value = lb.id;
      opt.textContent = lb.label;
      if (lb.is_default) opt.selected = true;
      logBackendEl.appendChild(opt);
    }
  } catch {
    // Non-fatal — selectors stay empty; fetch still works with server default
  }
}

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
        <p>Try a wider time range, clear the trace filter, or remove the component filter.</p>
      </div>`;
    paginationEl.style.display = 'none';
    updateSelectionBar();
    return;
  }

  const allPageSelected = records.length > 0 && records.every(r => selectedIds.has(r.file_trace_id));

  const rows = records.map(r => {
    const checked = selectedIds.has(r.file_trace_id) ? 'checked' : '';
    const traceId = (r.file_trace_id ?? '').replace(/"/g, '&quot;');
    // Trace cell: expandable raw CloudWatch/log context when present (XSS-safe).
    const traceCell = r.raw_payload
      ? `<details class="raw-payload"><summary>${fmt(r.file_trace_id)}</summary>` +
        `<pre>${fmt(JSON.stringify(r.raw_payload, null, 2))}</pre></details>`
      : fmt(r.file_trace_id);
    return `
      <tr>
        <td><input type="checkbox" class="row-check" data-id="${traceId}" ${checked} aria-label="Select record ${traceId}"/></td>
        <td>${traceCell}</td>
        <td><span class="tag tag-component">${fmt(r.component_name)}</span></td>
        <td class="message-cell">${fmt(r.message)}</td>
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
            <th>Message</th>
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

  document.getElementById('select-all').addEventListener('change', onSelectAll);
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
    analyzePanel.style.display = 'none';
  } else {
    selectionBar.classList.add('visible');
    selectionCount.textContent = `${count} record${count !== 1 ? 's' : ''} selected`;
    analyzeCount.textContent = count;
    analyzePanel.style.display = 'block';
    analyzeResult.style.display = 'none';
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
  const dataSource = dataSourceEl.value || null;
  const traceId = traceIdEl.value.trim();

  const body = { time_range: range, component, data_source: dataSource };
  if (traceId) body.trace_id = traceId;

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
    selectedIds.clear();

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

// ── Analyze ────────────────────────────────────────────────────────────────
async function analyzeSelected() {
  analyzeBtn.disabled = true;
  analyzeSpinner.style.display = 'inline-block';
  analyzeResult.style.display = 'none';

  const selected = allRecords.filter(r => selectedIds.has(r.file_trace_id));
  const logBackend = logBackendEl.value || null;

  analyzeResult.style.display = 'block';
  analyzeResult.innerHTML = '<strong>Analyzing…</strong><pre class="rca-output"></pre>';
  const out = analyzeResult.querySelector('.rca-output');
  const heading = analyzeResult.querySelector('strong');

  try {
    const resp = await fetch('/api/analyze/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        time_range: timeRangeEl.value,
        records: selected,
        log_backend: logBackend,
      }),
    });

    if (!resp.ok) {
      const detail = await resp.json().catch(() => ({}));
      throw new Error(detail.detail ?? `Server error ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let text = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      text += decoder.decode(value, { stream: true });
      out.textContent = text;
      out.scrollTop = out.scrollHeight;
    }
    heading.textContent = 'Root cause analysis';
  } catch (err) {
    analyzeResult.innerHTML = `<span style="color:var(--danger)">Analyze failed: ${err.message}</span>`;
  } finally {
    analyzeBtn.disabled = false;
    analyzeSpinner.style.display = 'none';
  }
}

// ── Wire up RCA events ─────────────────────────────────────────────────────
timeRangeEl.addEventListener('change', () => {
  customDatesEl.classList.toggle('visible', timeRangeEl.value === 'custom');
});

fetchBtn.addEventListener('click', fetchFailures);
analyzeBtn.addEventListener('click', analyzeSelected);

pageSizeEl.addEventListener('change', () => {
  pageSize = Number(pageSizeEl.value);
  currentPage = 1;
  renderTable();
});

clearSelectionBtn.addEventListener('click', () => {
  selectedIds.clear();
  renderTable();
});

// ── GitHub Integration ─────────────────────────────────────────────────────

const githubNotConfigured = document.getElementById('github-not-configured');
const githubContent       = document.getElementById('github-content');
const githubPrsList       = document.getElementById('github-prs-list');
const githubPrStateGroup  = document.getElementById('github-pr-state-group');
const githubPrsRefresh    = document.getElementById('github-prs-refresh');
const codeReviewSection   = document.getElementById('code-review-section');
const codeReviewTarget    = document.getElementById('code-review-target');
const codeReviewBody      = document.getElementById('code-review-body');
const codeReviewClose     = document.getElementById('code-review-close');
const postToPrPanel       = document.getElementById('post-to-pr-panel');
const postToPrBtn         = document.getElementById('post-to-pr-btn');
const postToPrSpinner     = document.getElementById('post-to-pr-spinner');
const postToPrResult      = document.getElementById('post-to-pr-result');

let githubPrState = 'open';
let githubLoaded = false;
let currentReviewData = null;
let currentPrNumber = null;

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function loadGithubPullRequests() {
  githubLoaded = true;
  githubPrsList.innerHTML = '<p class="github-empty">Loading…</p>';
  try {
    const resp = await fetch(`/api/github/pull-requests?state=${githubPrState}`);
    const data = await resp.json();

    if (data.error) {
      if (data.error.includes('not configured') || !resp.ok) {
        githubNotConfigured.classList.remove('hidden');
        githubContent.classList.add('hidden');
        return;
      }
      githubPrsList.innerHTML = `<p class="github-error">${escHtml(data.error)}</p>`;
      return;
    }

    githubNotConfigured.classList.add('hidden');
    githubContent.classList.remove('hidden');

    if (!data.pull_requests || data.pull_requests.length === 0) {
      githubPrsList.innerHTML = '<p class="github-empty">No pull requests found.</p>';
      return;
    }

    githubPrsList.innerHTML = '';
    data.pull_requests.forEach((pr) => {
      const row = document.createElement('div');
      row.className = 'github-pr-item';

      const num = document.createElement('span');
      num.className = 'github-pr-number';
      num.textContent = `#${pr.number}`;
      row.appendChild(num);

      const titleEl = pr.url ? document.createElement('a') : document.createElement('span');
      titleEl.className = 'github-pr-title';
      titleEl.textContent = pr.title || '(no title)';
      if (pr.url) { titleEl.href = pr.url; titleEl.target = '_blank'; titleEl.rel = 'noopener noreferrer'; }
      row.appendChild(titleEl);

      const state = document.createElement('span');
      state.className = `github-pr-state github-pr-state--${pr.state}`;
      state.textContent = pr.state;
      row.appendChild(state);

      const reviewBtn = document.createElement('button');
      reviewBtn.className = 'btn btn-sm';
      reviewBtn.textContent = 'AI Review';
      reviewBtn.addEventListener('click', () => runPrReview(pr.number));
      row.appendChild(reviewBtn);

      githubPrsList.appendChild(row);
    });
  } catch (e) {
    githubPrsList.innerHTML = `<p class="github-error">Failed to load pull requests: ${escHtml(e.message)}</p>`;
  }
}

const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

async function runPrReview(prNumber) {
  currentPrNumber = prNumber;
  currentReviewData = null;
  codeReviewSection.classList.remove('hidden');
  codeReviewTarget.textContent = `PR #${prNumber}`;
  codeReviewBody.innerHTML = '<p class="github-empty">Reviewing… this may take a minute.</p>';
  postToPrPanel.classList.add('hidden');
  postToPrResult.classList.add('hidden');
  codeReviewSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  try {
    const resp = await fetch(`/api/github/pull-requests/${prNumber}/review`);
    const data = await resp.json();

    if (data.error) {
      codeReviewBody.innerHTML = `<p class="github-error">${escHtml(data.error)}</p>`;
      return;
    }

    currentReviewData = data;
    renderReviewFindings(data);
    postToPrPanel.classList.remove('hidden');
    postToPrResult.classList.add('hidden');
    postToPrResult.textContent = '';
  } catch (e) {
    codeReviewBody.innerHTML = `<p class="github-error">Review failed: ${escHtml(e.message)}</p>`;
  }
}

function renderReviewFindings(data) {
  codeReviewBody.innerHTML = '';

  if (data.summary) {
    const summary = document.createElement('p');
    summary.className = 'code-review-summary';
    summary.textContent = data.summary;
    codeReviewBody.appendChild(summary);
  }

  const findings = (data.findings || []).slice()
    .sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9));

  if (findings.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'github-empty';
    empty.textContent = 'No issues found.';
    codeReviewBody.appendChild(empty);
    return;
  }

  findings.forEach((f) => {
    const item = document.createElement('div');
    item.className = `code-review-finding code-review-finding--${f.severity || 'info'}`;

    const header = document.createElement('div');
    header.className = 'code-review-finding-header';

    const sev = document.createElement('span');
    sev.className = `code-review-severity code-review-severity--${f.severity || 'info'}`;
    sev.textContent = (f.severity || 'info').toUpperCase();
    header.appendChild(sev);

    const cat = document.createElement('span');
    cat.className = 'code-review-category';
    cat.textContent = (f.category || '').replace(/_/g, ' ');
    header.appendChild(cat);

    const title = document.createElement('span');
    title.className = 'code-review-title';
    title.textContent = f.title || '';
    header.appendChild(title);

    item.appendChild(header);

    if (f.file) {
      const loc = document.createElement('div');
      loc.className = 'code-review-location';
      loc.textContent = f.line ? `${f.file}:${f.line}` : f.file;
      item.appendChild(loc);
    }

    if (f.description) {
      const desc = document.createElement('p');
      desc.className = 'code-review-description';
      desc.textContent = f.description;
      item.appendChild(desc);
    }

    if (f.recommendation) {
      const rec = document.createElement('p');
      rec.className = 'code-review-recommendation';
      rec.innerHTML = `<strong>Recommendation:</strong> ${escHtml(f.recommendation)}`;
      item.appendChild(rec);
    }

    codeReviewBody.appendChild(item);
  });
}

postToPrBtn.addEventListener('click', async () => {
  if (!currentReviewData || currentPrNumber === null) return;

  const confirmed = window.confirm(
    `Post this AI review onto PR #${currentPrNumber} as a GitHub review?\n\n` +
    'Re-posting will create a new review each time.'
  );
  if (!confirmed) return;

  postToPrBtn.disabled = true;
  postToPrSpinner.classList.remove('hidden');
  postToPrResult.classList.add('hidden');
  postToPrResult.textContent = '';

  try {
    const resp = await fetch(`/api/github/pull-requests/${currentPrNumber}/review/comments`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentReviewData),
    });
    const result = await resp.json();

    postToPrResult.classList.remove('hidden');
    if (result.posted) {
      postToPrResult.className = 'post-result post-result--success';
      const inline = result.inline_comment_count;
      const summary = result.summary_only_count;
      postToPrResult.innerHTML =
        `Review posted: ${inline} inline comment${inline !== 1 ? 's' : ''}, ` +
        `${summary} in summary. ` +
        (result.review_url
          ? `<a href="${escHtml(result.review_url)}" target="_blank" rel="noopener noreferrer">View on GitHub</a>`
          : '');
    } else {
      postToPrResult.className = 'post-result post-result--error';
      postToPrResult.textContent = `Failed to post: ${result.error || 'unknown error'}`;
    }
  } catch (e) {
    postToPrResult.classList.remove('hidden');
    postToPrResult.className = 'post-result post-result--error';
    postToPrResult.textContent = `Failed to post: ${e.message}`;
  } finally {
    postToPrBtn.disabled = false;
    postToPrSpinner.classList.add('hidden');
  }
});

codeReviewClose.addEventListener('click', () => {
  codeReviewSection.classList.add('hidden');
  codeReviewBody.innerHTML = '';
  postToPrPanel.classList.add('hidden');
  postToPrResult.classList.add('hidden');
  currentReviewData = null;
  currentPrNumber = null;
});

githubPrsRefresh.addEventListener('click', loadGithubPullRequests);

githubPrStateGroup.addEventListener('click', (e) => {
  const btn = e.target.closest('.btn');
  if (!btn || !btn.dataset.state) return;
  githubPrStateGroup.querySelectorAll('.btn').forEach((b) => b.classList.remove('active'));
  btn.classList.add('active');
  githubPrState = btn.dataset.state;
  loadGithubPullRequests();
});

// ── Config Page ────────────────────────────────────────────────────────────

const MASK_SENTINEL = '••••••••';

const awsStatusBadge       = document.getElementById('aws-status-badge');
const awsKeyIdInput        = document.getElementById('config-aws-key-id');
const awsSecretInput       = document.getElementById('config-aws-secret');
const awsSessionTokenInput = document.getElementById('config-aws-session-token');
const awsRegionInput       = document.getElementById('config-aws-region');
const awsKeyIdError        = document.getElementById('config-aws-key-id-error');
const awsSecretError       = document.getElementById('config-aws-secret-error');
const awsSaveForm          = document.getElementById('config-aws-form');
const awsFeedback          = document.getElementById('config-aws-feedback');

const cwStatusBadge        = document.getElementById('cloudwatch-status-badge');
const cwTimeoutInput       = document.getElementById('config-cw-timeout');
const cwLogGroupsError     = document.getElementById('config-cw-log-groups-error');
const cwTimeoutError       = document.getElementById('config-cw-timeout-error');
const cwSaveForm           = document.getElementById('config-cloudwatch-form');
const cwFeedback           = document.getElementById('config-cw-feedback');
const cwLgDropdown         = document.getElementById('config-cw-lg-dropdown');
const cwLgToggle           = document.getElementById('config-cw-lg-toggle');
const cwLgSummary          = document.getElementById('config-cw-lg-summary');
const cwLgPanel            = document.getElementById('config-cw-lg-panel');
const cwLgSearch           = document.getElementById('config-cw-lg-search');
const cwLgRefresh          = document.getElementById('config-cw-lg-refresh');
const cwLgStatus           = document.getElementById('config-cw-lg-status');
const cwLgList             = document.getElementById('config-cw-lg-list');

// CloudWatch log-group selection state (populated from AWS via the API).
let cwAllGroups = [];
const cwSelectedGroups = new Set();

const githubMcpStatusBadge = document.getElementById('github-mcp-status-badge');
const githubRepoInput      = document.getElementById('config-github-repo');
const githubTokenInput     = document.getElementById('config-github-token');
const githubBranchInput    = document.getElementById('config-github-branch');
const githubRepoError      = document.getElementById('config-github-repo-error');
const githubTokenError     = document.getElementById('config-github-token-error');
const githubMcpSaveForm    = document.getElementById('config-github-mcp-form');
const githubMcpFeedback    = document.getElementById('config-github-mcp-feedback');
const athenaStatusBadge    = document.getElementById('athena-status-badge');
const athenaDatabaseInput  = document.getElementById('config-athena-database');
const athenaTableInput     = document.getElementById('config-athena-table');
const athenaDatabaseError  = document.getElementById('config-athena-database-error');
const athenaTableError     = document.getElementById('config-athena-table-error');
const athenaSaveForm       = document.getElementById('config-athena-form');
const athenaFeedback       = document.getElementById('config-athena-feedback');

function _setBadge(badgeEl, configured) {
  badgeEl.textContent = configured ? 'Configured' : 'Not Configured';
  badgeEl.classList.toggle('config-status-badge--configured', configured);
  badgeEl.classList.toggle('config-status-badge--not-configured', !configured);
}

function _showFeedback(el, message, isError) {
  el.textContent = message;
  el.classList.remove('hidden', 'config-feedback--success', 'config-feedback--error');
  el.classList.add(isError ? 'config-feedback--error' : 'config-feedback--success');
}

function _clearFieldError(inputEl, errorEl) {
  errorEl.textContent = '';
  errorEl.classList.add('hidden');
  inputEl.classList.remove('config-field--invalid');
}

function _showFieldError(inputEl, errorEl, message) {
  errorEl.textContent = message;
  errorEl.classList.remove('hidden');
  inputEl.classList.add('config-field--invalid');
}

async function loadConfigPage() {
  try {
    const resp = await fetch('/api/config');
    const data = await resp.json();

    const aws = data.aws;
    awsKeyIdInput.value       = aws.access_key_id || '';
    awsSecretInput.value      = aws.secret_access_key || '';
    awsSessionTokenInput.value = aws.session_token || '';
    awsRegionInput.value      = aws.region || '';
    _setBadge(awsStatusBadge, aws.configured);

    const cw = data.cloudwatch || { configured: false, log_groups: [] };
    cwSelectedGroups.clear();
    (cw.log_groups || []).forEach(g => cwSelectedGroups.add(g));
    cwTimeoutInput.value = cw.query_timeout != null ? String(cw.query_timeout) : '';
    cwLgSearch.value = '';
    _setBadge(cwStatusBadge, cw.configured);
    if (aws.configured) {
      await fetchCwLogGroups();
    } else {
      cwAllGroups = [];
      cwLgList.innerHTML = '';
      cwLgStatus.textContent = 'Save AWS credentials to load log groups.';
      _cwUpdateSummary();
    }

    const github = data.github_mcp;
    githubRepoInput.value   = github.repo || '';
    githubTokenInput.value  = github.token || '';
    githubBranchInput.value = github.default_branch || '';
    _setBadge(githubMcpStatusBadge, github.configured);

    const athena = data.athena || { configured: false };
    athenaDatabaseInput.value = athena.database || '';
    athenaTableInput.value    = athena.table || '';
    _setBadge(athenaStatusBadge, athena.configured);

    await loadConfigProfiles();
    if (aws.configured) {
      await Promise.all(Object.values(healthPickers).map(p => p.load()));
    } else {
      Object.values(healthPickers).forEach(p => p.reset());
    }
  } catch {
    _showFeedback(awsFeedback, 'Failed to load configuration.', true);
  }
}

awsSaveForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  _clearFieldError(awsKeyIdInput, awsKeyIdError);
  _clearFieldError(awsSecretInput, awsSecretError);
  awsFeedback.classList.add('hidden');

  const keyId  = awsKeyIdInput.value.trim();
  const secret = awsSecretInput.value;
  const token  = awsSessionTokenInput.value;
  const region = awsRegionInput.value.trim();

  let valid = true;
  if (!keyId) {
    _showFieldError(awsKeyIdInput, awsKeyIdError, 'Access Key ID is required.');
    valid = false;
  }
  if (!secret) {
    _showFieldError(awsSecretInput, awsSecretError, 'Secret Access Key is required.');
    valid = false;
  }
  if (!valid) return;

  try {
    const resp = await fetch('/api/config/aws', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_key_id: keyId, secret_access_key: secret, session_token: token || undefined, region: region || undefined }),
    });
    const data = await resp.json();
    if (resp.ok && data.success) {
      _showFeedback(awsFeedback, 'AWS configuration saved.', false);
      await loadConfigPage();
    } else {
      _showFeedback(awsFeedback, data.detail ? JSON.stringify(data.detail) : 'Failed to save AWS configuration.', true);
    }
  } catch (err) {
    _showFeedback(awsFeedback, `Error: ${err.message}`, true);
  }
});

cwSaveForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  _clearFieldError(cwTimeoutInput, cwTimeoutError);
  cwLogGroupsError.classList.add('hidden');
  cwFeedback.classList.add('hidden');

  const logGroups = [...cwSelectedGroups];
  const timeoutRaw = cwTimeoutInput.value.trim();

  let valid = true;
  if (logGroups.length === 0) {
    cwLogGroupsError.textContent = 'Select at least one log group.';
    cwLogGroupsError.classList.remove('hidden');
    valid = false;
  }
  let timeout;
  if (timeoutRaw) {
    timeout = Number(timeoutRaw);
    if (!Number.isFinite(timeout) || timeout <= 0) {
      _showFieldError(cwTimeoutInput, cwTimeoutError, 'Timeout must be a positive number of seconds.');
      valid = false;
    }
  }
  if (!valid) return;

  const payload = { log_groups: logGroups };
  if (timeout !== undefined) payload.query_timeout = timeout;

  try {
    const resp = await fetch('/api/config/cloudwatch', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (resp.ok && data.success) {
      _showFeedback(cwFeedback, 'CloudWatch configuration saved.', false);
      await loadConfigPage();
    } else {
      _showFeedback(cwFeedback, data.detail ? JSON.stringify(data.detail) : 'Failed to save CloudWatch configuration.', true);
    }
  } catch (err) {
    _showFeedback(cwFeedback, `Error: ${err.message}`, true);
  }
});

// --- CloudWatch log-group multi-select (populated from AWS) ------------------

function _esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function _cwUpdateSummary() {
  const n = cwSelectedGroups.size;
  cwLgSummary.textContent = n === 0
    ? 'Select log groups'
    : (n === 1 ? [...cwSelectedGroups][0] : `${n} log groups selected`);
  if (cwAllGroups.length > 0) {
    cwLgStatus.textContent = `${cwAllGroups.length} available • ${n} selected`;
  }
}

function _cwVisibleGroups() {
  const all = [...cwAllGroups].sort();
  // Support "|"-separated AND terms, e.g. "onedbm|db11204" matches groups
  // whose name contains "onedbm" AND "db11204" anywhere.
  const terms = cwLgSearch.value.toLowerCase()
    .split('|')
    .map(t => t.trim())
    .filter(Boolean);
  if (terms.length === 0) return all;
  return all.filter(g => {
    const name = g.toLowerCase();
    return terms.every(t => name.includes(t));
  });
}

function _cwSyncSelectAll(visible) {
  const selectAll = document.getElementById('cw-lg-selectall');
  if (!selectAll) return;
  const selected = visible.filter(g => cwSelectedGroups.has(g)).length;
  selectAll.checked = visible.length > 0 && selected === visible.length;
  selectAll.indeterminate = selected > 0 && selected < visible.length;
}

function _renderCwLogGroups() {
  if (cwAllGroups.length === 0) {
    cwLgList.innerHTML = '';
    return;
  }
  const filter = cwLgSearch.value.trim();
  const visible = _cwVisibleGroups();
  if (visible.length === 0) {
    cwLgList.innerHTML = '<p class="cw-lg-empty">No log groups match the filter.</p>';
    return;
  }
  const header =
    `<label class="cw-lg-item cw-lg-selectall"><input type="checkbox" id="cw-lg-selectall" /> ` +
    `Select all${filter ? ' (filtered)' : ''} (${visible.length})</label>`;
  const items = visible.map((g, i) => {
    const checked = cwSelectedGroups.has(g) ? ' checked' : '';
    return `<label class="cw-lg-item"><input type="checkbox" data-lg="${_esc(g)}" id="cw-lg-${i}"${checked} /> ${_esc(g)}</label>`;
  }).join('');
  cwLgList.innerHTML = header + items;

  const selectAll = document.getElementById('cw-lg-selectall');
  _cwSyncSelectAll(visible);
  selectAll.addEventListener('change', () => {
    if (selectAll.checked) visible.forEach(g => cwSelectedGroups.add(g));
    else visible.forEach(g => cwSelectedGroups.delete(g));
    _renderCwLogGroups();
    _cwUpdateSummary();
  });

  cwLgList.querySelectorAll('input[data-lg]').forEach(cb => {
    cb.addEventListener('change', () => {
      const name = cb.getAttribute('data-lg');
      if (cb.checked) cwSelectedGroups.add(name); else cwSelectedGroups.delete(name);
      _cwSyncSelectAll(_cwVisibleGroups());
      _cwUpdateSummary();
    });
  });
}

async function fetchCwLogGroups() {
  cwLgStatus.textContent = 'Loading log groups…';
  cwLgRefresh.disabled = true;
  try {
    const resp = await fetch('/api/config/cloudwatch/log-groups');
    const data = await resp.json();
    if (resp.ok) {
      cwAllGroups = data.log_groups || [];
      // Drop any previously-saved selections that no longer exist in the account
      // so stale/invalid groups can't break the fetch query.
      if (cwAllGroups.length > 0) {
        const existing = new Set(cwAllGroups);
        [...cwSelectedGroups].forEach(g => { if (!existing.has(g)) cwSelectedGroups.delete(g); });
      }
      _renderCwLogGroups();
      if (cwAllGroups.length === 0) {
        cwLgStatus.textContent = 'No log groups found in this account/region.';
      }
      _cwUpdateSummary();
    } else {
      cwLgList.innerHTML = '';
      cwLgStatus.textContent = data.detail
        ? `Failed to load log groups: ${data.detail}`
        : 'Failed to load log groups.';
    }
  } catch (err) {
    cwLgList.innerHTML = '';
    cwLgStatus.textContent = `Error loading log groups: ${err.message}`;
  } finally {
    cwLgRefresh.disabled = false;
  }
}

cwLgToggle.addEventListener('click', () => cwLgPanel.classList.toggle('hidden'));
document.addEventListener('click', (e) => {
  if (!cwLgDropdown.contains(e.target)) cwLgPanel.classList.add('hidden');
});
cwLgSearch.addEventListener('input', _renderCwLogGroups);
cwLgRefresh.addEventListener('click', fetchCwLogGroups);

githubMcpSaveForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  _clearFieldError(githubRepoInput, githubRepoError);
  _clearFieldError(githubTokenInput, githubTokenError);
  githubMcpFeedback.classList.add('hidden');

  const repo   = githubRepoInput.value.trim();
  const token  = githubTokenInput.value;
  const branch = githubBranchInput.value.trim();

  let valid = true;
  if (!repo || !repo.includes('/')) {
    _showFieldError(githubRepoInput, githubRepoError, 'Repository must be in owner/repo format.');
    valid = false;
  }
  if (!token) {
    _showFieldError(githubTokenInput, githubTokenError, 'Personal Access Token is required.');
    valid = false;
  }
  if (!valid) return;

  try {
    const resp = await fetch('/api/config/github-mcp', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ repo, token, default_branch: branch || undefined }),
    });
    const data = await resp.json();
    if (resp.ok && data.success) {
      _showFeedback(githubMcpFeedback, 'GitHub MCP configuration saved.', false);
      await loadConfigPage();
    } else {
      _showFeedback(githubMcpFeedback, data.detail ? JSON.stringify(data.detail) : 'Failed to save GitHub MCP configuration.', true);
    }
  } catch (err) {
    _showFeedback(githubMcpFeedback, `Error: ${err.message}`, true);
  }
});

athenaSaveForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  _clearFieldError(athenaDatabaseInput, athenaDatabaseError);
  _clearFieldError(athenaTableInput, athenaTableError);
  athenaFeedback.classList.add('hidden');

  const database = athenaDatabaseInput.value.trim();
  const table    = athenaTableInput.value.trim();

  let valid = true;
  if (!database) {
    _showFieldError(athenaDatabaseInput, athenaDatabaseError, 'Database is required.');
    valid = false;
  }
  if (!table) {
    _showFieldError(athenaTableInput, athenaTableError, 'Table is required.');
    valid = false;
  }
  if (!valid) return;

  try {
    const resp = await fetch('/api/config/athena', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ database, table }),
    });
    const data = await resp.json();
    if (resp.ok && data.success) {
      _showFeedback(athenaFeedback, 'Athena configuration saved.', false);
      await loadConfigPage();
    } else {
      _showFeedback(athenaFeedback, data.detail ? JSON.stringify(data.detail) : 'Failed to save Athena configuration.', true);
    }
  } catch (err) {
    _showFeedback(athenaFeedback, `Error: ${err.message}`, true);
  }
});

// ── Service Health dashboard (feature 021) ──────────────────────────────────

const healthGrid    = document.getElementById('health-grid');
const healthStatusEl = document.getElementById('health-status');
const healthWindowSel = document.getElementById('health-window');
const healthRefreshBtn = document.getElementById('health-refresh');
const healthSpinner = document.getElementById('health-spinner');
const healthTotalEl = document.getElementById('health-total');
const healthStartEl = document.getElementById('health-start');
const healthEndEl = document.getElementById('health-end');
const healthRangeEls = [document.getElementById('health-range'), document.getElementById('health-range-end')];
const healthProfileSel = document.getElementById('health-profile');
const healthExportBtn = document.getElementById('health-export');
const healthExportSpinner = document.getElementById('health-export-spinner');

// The actual lookback bounds + profile of the currently displayed results, captured
// from the last successful load so the CSV export queries the same range.
let _healthRange = null;  // { start, end, profile }

async function loadHealthTabProfiles() {
  const previous = healthProfileSel.value;
  const profiles = await fetchProfiles();
  const names = profiles.map(p => p.name);
  healthProfileSel.innerHTML = names.length
    ? names.map(n => `<option value="${_esc(n)}">${_esc(n)}</option>`).join('')
    : '<option value="">No profiles</option>';
  if (names.includes(previous)) healthProfileSel.value = previous;
}

function _renderHealthTotal(total, count) {
  if (count === 0) {
    healthTotalEl.classList.add('hidden');
    return;
  }
  healthTotalEl.textContent = `${total} failure${total === 1 ? '' : 's'} total`;
  healthTotalEl.classList.toggle('health-total-nonzero', total > 0);
  healthTotalEl.classList.remove('hidden');
}

const HEALTH_SERVICE_LABELS = {
  glue_job: 'Glue Job',
  glue_workflow: 'Glue Workflow',
  lambda_function: 'Lambda',
  datasync_task: 'DataSync',
};

function _healthCls(r) {
  if (r.status === 'down') return 'health-red';
  if (r.status === 'unknown') return 'health-gray';
  return r.failure_count > 0 ? 'health-amber' : 'health-green';
}

let _healthResults = [];

function _renderHealthCards(results) {
  _healthResults = results;
  if (results.length === 0) {
    healthGrid.innerHTML = '';
    healthStatusEl.textContent = 'No services configured. Add resources on the Config tab.';
    return;
  }
  healthStatusEl.textContent = 'Click a card for run history and failure reasons.';
  healthGrid.innerHTML = results.map((r, i) => {
    const cls = _healthCls(r);
    const fails = `${r.failure_count} failure${r.failure_count === 1 ? '' : 's'}`;
    const detail = r.detail ? `<div class="health-card-detail">${_esc(r.detail)}</div>` : '';
    return `<div class="health-card ${cls}" data-idx="${i}" role="button" tabindex="0" title="View details for ${_esc(r.label)}">
      <div class="health-card-top"><span class="health-dot ${cls}"></span><span class="health-card-type">${HEALTH_SERVICE_LABELS[r.service_type] || r.service_type}</span></div>
      <div class="health-card-name" title="${_esc(r.id)}">${_esc(r.label)}</div>
      <div class="health-card-meta"><span class="health-card-status">${_esc(r.status)}</span><span>${fails}</span></div>
      ${detail}
    </div>`;
  }).join('');
}

function _healthUrl() {
  const profile = healthProfileSel.value;
  const profileParam = profile ? `&profile=${encodeURIComponent(profile)}` : '';
  const win = healthWindowSel.value;
  if (win !== 'custom') {
    return `/api/health/services?window=${encodeURIComponent(win)}${profileParam}`;
  }
  if (!healthStartEl.value || !healthEndEl.value) return null;
  const start = `${healthStartEl.value}T00:00:00Z`;
  const end = `${healthEndEl.value}T23:59:59Z`;
  return `/api/health/services?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}${profileParam}`;
}

async function loadServiceHealth() {
  const url = _healthUrl();
  if (url === null) {
    healthStatusEl.textContent = 'Pick a start and end date.';
    return;
  }
  healthSpinner.classList.remove('hidden');
  healthRefreshBtn.disabled = true;
  healthStatusEl.textContent = 'Loading…';
  try {
    const resp = await fetch(url);
    const data = await resp.json();
    if (resp.ok) {
      const results = data.results || [];
      _renderHealthCards(results);
      _renderHealthTotal(data.total_failures || 0, results.length);
      _healthRange = { start: data.start, end: data.end, profile: data.profile || healthProfileSel.value };
    } else {
      healthGrid.innerHTML = '';
      _healthRange = null;
      _renderHealthTotal(0, 0);
      healthStatusEl.textContent = data.detail ? `Failed: ${JSON.stringify(data.detail)}` : 'Failed to load health.';
    }
  } catch (err) {
    healthGrid.innerHTML = '';
    healthStatusEl.textContent = `Error: ${err.message}`;
  } finally {
    healthSpinner.classList.add('hidden');
    healthRefreshBtn.disabled = false;
  }
}

// ── CSV export: server details + failure count + unique failure messages ────────

function _csvCell(v) {
  const s = v == null ? '' : String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function _downloadCsv(filename, rows) {
  // Prepend a BOM so Excel opens the UTF-8 file with the right encoding.
  const csv = '﻿' + rows.map(r => r.map(_csvCell).join(',')).join('\r\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Fetch failure logs for one server and collapse them to unique messages, keyed by
// signature_hash when present (else the message text), each with an occurrence count.
async function _fetchUniqueFailures(server, range) {
  const resp = await fetch('/api/health/services/failures', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      service_type: server.service_type,
      id: server.id,
      label: server.label,
      start: range.start,
      end: range.end,
    }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.detail ? JSON.stringify(data.detail) : 'fetch failed');
  const byKey = new Map();
  for (const r of data.records || []) {
    const msg = (r.message || '(no message)').trim();
    const key = r.signature_hash || msg;
    const entry = byKey.get(key);
    if (entry) entry.count += 1;
    else byKey.set(key, { message: msg, count: 1 });
  }
  return [...byKey.values()];
}

async function exportHealthCsv() {
  if (!_healthResults.length || !_healthRange) {
    healthStatusEl.textContent = 'Load health results before exporting.';
    return;
  }
  healthExportBtn.disabled = true;
  healthExportSpinner.classList.remove('hidden');
  const profile = _healthRange.profile || '';
  const rows = [[
    'Profile', 'Service Type', 'Server', 'Server ID', 'Status',
    'Failure Count', 'Unique Failure Count', 'Failure Message', 'Occurrences',
  ]];
  try {
    for (let i = 0; i < _healthResults.length; i++) {
      const s = _healthResults[i];
      healthStatusEl.textContent = `Exporting… fetching failures ${i + 1}/${_healthResults.length}`;
      const typeLabel = HEALTH_SERVICE_LABELS[s.service_type] || s.service_type;
      let unique = [];
      let note = '';
      try {
        unique = await _fetchUniqueFailures(s, _healthRange);
      } catch (err) {
        note = `fetch failed: ${err.message}`;
      }
      const base = [profile, typeLabel, s.label, s.id, s.status, s.failure_count, unique.length];
      if (unique.length === 0) {
        rows.push([...base, note, note ? '' : 0]);
      } else {
        for (const u of unique) rows.push([...base, u.message, u.count]);
      }
    }
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const safeProfile = (profile || 'health').replace(/[^\w.-]+/g, '_');
    _downloadCsv(`service-health-${safeProfile}-${stamp}.csv`, rows);
    healthStatusEl.textContent = `Exported ${_healthResults.length} server(s) to CSV.`;
  } catch (err) {
    healthStatusEl.textContent = `Export failed: ${err.message}`;
  } finally {
    healthExportBtn.disabled = false;
    healthExportSpinner.classList.add('hidden');
  }
}

function _onHealthWindowChange() {
  const custom = healthWindowSel.value === 'custom';
  healthRangeEls.forEach(el => el.classList.toggle('hidden', !custom));
  if (custom) {
    if (!healthStartEl.value || !healthEndEl.value) {
      const now = new Date();
      healthStartEl.value = _ymd(new Date(now.getTime() - 7 * 86400000));
      healthEndEl.value = _ymd(now);
    }
  }
  loadServiceHealth();
}

healthWindowSel.addEventListener('change', _onHealthWindowChange);
healthStartEl.addEventListener('change', loadServiceHealth);
healthEndEl.addEventListener('change', loadServiceHealth);
healthProfileSel.addEventListener('change', loadServiceHealth);
healthRefreshBtn.addEventListener('click', loadServiceHealth);
healthExportBtn.addEventListener('click', exportHealthCsv);

// ── Drill-down: run history + failure reasons for one resource ──────────────

const healthModal = document.getElementById('health-detail-modal');
const healthDetailType = document.getElementById('health-detail-type');
const healthDetailTitle = document.getElementById('health-detail-title');
const healthDetailStart = document.getElementById('health-detail-start');
const healthDetailEnd = document.getElementById('health-detail-end');
const healthDetailLoad = document.getElementById('health-detail-load');
const healthDetailSpinner = document.getElementById('health-detail-spinner');
const healthDetailBody = document.getElementById('health-detail-body');
const healthDetailFailures = document.getElementById('health-detail-failures');
const healthFailuresBtn = document.getElementById('health-detail-fetch-failures');
const healthFailuresSpinner = document.getElementById('health-failures-spinner');

let _healthDetailTarget = null;  // { service_type, id, label }

function _ymd(d) { return d.toISOString().slice(0, 10); }
function _fmtTs(s) { return s ? new Date(s).toLocaleString() : '—'; }

function _detailRange() {
  return {
    start: `${healthDetailStart.value}T00:00:00Z`,
    end: `${healthDetailEnd.value}T23:59:59Z`,
  };
}

// The From/To dates the Health tab is currently set to — a custom range verbatim,
// or the equivalent day span for a preset window. The drill-down opens with these
// so the "info" view matches the range you're already looking at.
function _healthTabDateRange() {
  const now = new Date();
  if (healthWindowSel.value === 'custom' && healthStartEl.value && healthEndEl.value) {
    return { start: healthStartEl.value, end: healthEndEl.value };
  }
  const daysBack = { '1h': 0, '24h': 1, '7d': 7 }[healthWindowSel.value] ?? 7;
  return { start: _ymd(new Date(now.getTime() - daysBack * 86400000)), end: _ymd(now) };
}

function openHealthDetail(result) {
  _healthDetailTarget = { service_type: result.service_type, id: result.id, label: result.label };
  healthDetailType.textContent = HEALTH_SERVICE_LABELS[result.service_type] || result.service_type;
  healthDetailTitle.textContent = result.label;
  const range = _healthTabDateRange();
  healthDetailStart.value = range.start;
  healthDetailEnd.value = range.end;
  healthDetailBody.innerHTML = '';
  healthDetailFailures.innerHTML = '';
  healthModal.classList.remove('hidden');
  loadHealthHistory();
}

function closeHealthDetail() {
  healthModal.classList.add('hidden');
  _healthDetailTarget = null;
}

function _renderRuns(runs) {
  const rows = runs.map(r => `<tr class="${r.is_failure ? 'health-run-fail' : ''}">
    <td>${_esc(r.run_id || '—')}</td>
    <td class="health-run-status">${_esc(r.status || '—')}</td>
    <td>${_fmtTs(r.started_at)}</td>
    <td>${_fmtTs(r.ended_at)}</td>
    <td>${r.detail ? _esc(r.detail) : ''}</td>
  </tr>`).join('');
  return `<table class="health-runs">
    <thead><tr><th>Run</th><th>Status</th><th>Started</th><th>Ended</th><th>Detail</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

async function loadHealthHistory() {
  if (!_healthDetailTarget) return;
  healthDetailSpinner.classList.remove('hidden');
  healthDetailLoad.disabled = true;
  healthDetailBody.innerHTML = '<div class="health-msg">Loading history…</div>';
  try {
    const resp = await fetch('/api/health/services/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ..._healthDetailTarget, ..._detailRange() }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      healthDetailBody.innerHTML = `<div class="health-msg">${data.detail ? _esc(JSON.stringify(data.detail)) : 'Failed to load history.'}</div>`;
      return;
    }
    const runs = data.runs || [];
    if (runs.length > 0) {
      healthDetailBody.innerHTML = _renderRuns(runs);
    } else {
      healthDetailBody.innerHTML = `<div class="health-msg">${data.detail ? _esc(data.detail) : 'No failed runs in this date range.'}</div>`;
    }
  } catch (err) {
    healthDetailBody.innerHTML = `<div class="health-msg">Error: ${_esc(err.message)}</div>`;
  } finally {
    healthDetailSpinner.classList.add('hidden');
    healthDetailLoad.disabled = false;
  }
}

function _renderFailures(records) {
  if (records.length === 0) {
    return '<div class="health-msg">No failure logs found in CloudWatch for this range.</div>';
  }
  const cards = records.map(r => `<div class="health-failure-card">
    <div class="trace">${_esc(r.file_trace_id || '—')}${r.event_created_ts ? ' · ' + _fmtTs(r.event_created_ts) : ''}</div>
    <pre>${_esc(r.message || '(no message)')}</pre>
  </div>`).join('');
  return `<h4>Failure reasons (${records.length})</h4>${cards}`;
}

async function fetchHealthFailures() {
  if (!_healthDetailTarget) return;
  healthFailuresSpinner.classList.remove('hidden');
  healthFailuresBtn.disabled = true;
  healthDetailFailures.innerHTML = '<div class="health-msg">Querying CloudWatch for failure reasons…</div>';
  try {
    const resp = await fetch('/api/health/services/failures', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ..._healthDetailTarget, ..._detailRange() }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      healthDetailFailures.innerHTML = `<div class="health-msg">${data.detail ? _esc(JSON.stringify(data.detail)) : 'Failed to fetch failures.'}</div>`;
      return;
    }
    healthDetailFailures.innerHTML = _renderFailures(data.records || []);
  } catch (err) {
    healthDetailFailures.innerHTML = `<div class="health-msg">Error: ${_esc(err.message)}</div>`;
  } finally {
    healthFailuresSpinner.classList.add('hidden');
    healthFailuresBtn.disabled = false;
  }
}

function _openFromCard(el) {
  const idx = Number(el.dataset.idx);
  const result = _healthResults[idx];
  if (result) openHealthDetail(result);
}

healthGrid.addEventListener('click', (e) => {
  const card = e.target.closest('.health-card');
  if (card) _openFromCard(card);
});
healthGrid.addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const card = e.target.closest('.health-card');
  if (card) { e.preventDefault(); _openFromCard(card); }
});
healthDetailLoad.addEventListener('click', loadHealthHistory);
healthFailuresBtn.addEventListener('click', fetchHealthFailures);
document.getElementById('health-detail-close').addEventListener('click', closeHealthDetail);
healthModal.addEventListener('click', (e) => { if (e.target === healthModal) closeHealthDetail(); });
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !healthModal.classList.contains('hidden')) closeHealthDetail();
});

// ── Health resource pickers (Config tab) — one reusable multi-select factory ──

function createHealthPicker(service, url) {
  const el = suffix => document.getElementById(`hp-${service}-${suffix}`);
  const dropdown = el('dropdown');
  const toggle = el('toggle');
  const summary = el('summary');
  const panel = el('panel');
  const search = el('search');
  const refresh = el('refresh');
  const status = el('status');
  const list = el('list');
  const placeholder = summary.textContent;

  let all = [];                // [{id,label}]
  const selected = new Set();  // ids
  const labels = new Map();    // id -> label

  function updateSummary() {
    const n = selected.size;
    summary.textContent = n === 0
      ? placeholder
      : (n === 1 ? (labels.get([...selected][0]) || [...selected][0]) : `${n} selected`);
    if (all.length > 0) status.textContent = `${all.length} available • ${n} selected`;
  }

  function visible() {
    const terms = search.value.toLowerCase().split('|').map(t => t.trim()).filter(Boolean);
    const sorted = [...all].sort((a, b) => a.label.localeCompare(b.label));
    if (terms.length === 0) return sorted;
    return sorted.filter(r => terms.every(t => r.label.toLowerCase().includes(t)));
  }

  function render() {
    if (all.length === 0) { list.innerHTML = ''; return; }
    const vis = visible();
    if (vis.length === 0) { list.innerHTML = '<p class="cw-lg-empty">No matches.</p>'; return; }
    list.innerHTML = vis.map(r => {
      const checked = selected.has(r.id) ? ' checked' : '';
      return `<label class="cw-lg-item"><input type="checkbox" data-id="${_esc(r.id)}"${checked} /> ${_esc(r.label)}</label>`;
    }).join('');
    list.querySelectorAll('input[data-id]').forEach(cb => {
      cb.addEventListener('change', () => {
        const id = cb.getAttribute('data-id');
        if (cb.checked) selected.add(id); else selected.delete(id);
        updateSummary();
      });
    });
  }

  async function load() {
    status.textContent = 'Loading…';
    refresh.disabled = true;
    try {
      const resp = await fetch(url);
      const data = await resp.json();
      if (resp.ok) {
        all = data.resources || [];
        all.forEach(r => labels.set(r.id, r.label));
        const ids = new Set(all.map(r => r.id));
        [...selected].forEach(id => { if (!ids.has(id)) selected.delete(id); });
        render();
        if (all.length === 0) status.textContent = 'None found in this account/region.';
        updateSummary();
      } else {
        list.innerHTML = '';
        status.textContent = data.detail ? `Failed: ${data.detail}` : 'Failed to load.';
      }
    } catch (err) {
      list.innerHTML = '';
      status.textContent = `Error: ${err.message}`;
    } finally {
      refresh.disabled = false;
    }
  }

  toggle.addEventListener('click', () => panel.classList.toggle('hidden'));
  document.addEventListener('click', e => { if (!dropdown.contains(e.target)) panel.classList.add('hidden'); });
  search.addEventListener('input', render);
  refresh.addEventListener('click', load);

  return {
    setSelection(items) {
      selected.clear();
      (items || []).forEach(it => {
        const id = typeof it === 'string' ? it : it.id;
        const label = typeof it === 'string' ? it : it.label;
        selected.add(id);
        labels.set(id, label);
      });
      updateSummary();
    },
    reset() {
      all = [];
      selected.clear();
      list.innerHTML = '';
      status.textContent = 'Save AWS credentials to load.';
      updateSummary();
    },
    load,
    getIds() { return [...selected]; },
    getResources() { return [...selected].map(id => ({ id, label: labels.get(id) || id })); },
  };
}

const healthPickers = {
  glue_jobs: createHealthPicker('glue_jobs', '/api/config/health/glue-jobs'),
  glue_workflows: createHealthPicker('glue_workflows', '/api/config/health/glue-workflows'),
  lambda_functions: createHealthPicker('lambda_functions', '/api/config/health/lambda-functions'),
  datasync_tasks: createHealthPicker('datasync_tasks', '/api/config/health/datasync-tasks'),
};

// ── Health profiles (Config tab) ────────────────────────────────────────────

const configProfileSelect = document.getElementById('config-profile-select');
const configProfileEmpty = document.getElementById('config-profile-empty');
const configHealthSaveBtn = document.getElementById('config-health-save');
const healthProfileFeedback = document.getElementById('config-health-feedback');

let _configProfiles = [];  // [{name, glue_jobs, ...}]

async function fetchProfiles() {
  const resp = await fetch('/api/config/health/profiles');
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.profiles || [];
}

function _applyProfileToPickers(profile) {
  healthPickers.glue_jobs.setSelection(profile ? profile.glue_jobs : []);
  healthPickers.glue_workflows.setSelection(profile ? profile.glue_workflows : []);
  healthPickers.lambda_functions.setSelection(profile ? profile.lambda_functions : []);
  healthPickers.datasync_tasks.setSelection(profile ? profile.datasync_tasks : []);
}

function _currentConfigProfile() {
  return _configProfiles.find(p => p.name === configProfileSelect.value) || null;
}

function _renderConfigProfiles(selectName) {
  const names = _configProfiles.map(p => p.name);
  configProfileSelect.innerHTML = names.map(n => `<option value="${_esc(n)}">${_esc(n)}</option>`).join('');
  const hasProfiles = names.length > 0;
  configProfileSelect.classList.toggle('hidden', !hasProfiles);
  configProfileEmpty.classList.toggle('hidden', hasProfiles);
  configHealthSaveBtn.disabled = !hasProfiles;
  _setBadge(document.getElementById('health-status-badge'), hasProfiles);
  ['config-profile-rename', 'config-profile-delete'].forEach(id => {
    document.getElementById(id).disabled = !hasProfiles;
  });
  if (hasProfiles) {
    configProfileSelect.value = names.includes(selectName) ? selectName : names[0];
  }
  _applyProfileToPickers(_currentConfigProfile());
}

async function loadConfigProfiles(selectName) {
  _configProfiles = await fetchProfiles();
  _renderConfigProfiles(selectName || configProfileSelect.value);
}

async function saveHealthConfig() {
  const profile = _currentConfigProfile();
  if (!profile) {
    _showFeedback(healthProfileFeedback, 'Create a profile first.', true);
    return;
  }
  const payload = {
    name: profile.name,
    glue_jobs: healthPickers.glue_jobs.getIds(),
    glue_workflows: healthPickers.glue_workflows.getIds(),
    lambda_functions: healthPickers.lambda_functions.getIds(),
    datasync_tasks: healthPickers.datasync_tasks.getResources(),
  };
  try {
    const resp = await fetch('/api/config/health/profiles', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (resp.ok) {
      _showFeedback(healthProfileFeedback, `Profile "${profile.name}" saved.`, false);
      await loadConfigProfiles(profile.name);
    } else {
      _showFeedback(healthProfileFeedback, data.detail ? JSON.stringify(data.detail) : 'Failed to save profile.', true);
    }
  } catch (err) {
    _showFeedback(healthProfileFeedback, `Error: ${err.message}`, true);
  }
}

async function createProfile() {
  const name = (window.prompt('New profile name:') || '').trim();
  if (!name) return;
  try {
    const resp = await fetch('/api/config/health/profiles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const data = await resp.json();
    if (resp.ok) {
      await loadConfigProfiles(data.name);
      _showFeedback(healthProfileFeedback, `Profile "${data.name}" created.`, false);
    } else {
      _showFeedback(healthProfileFeedback, data.detail || 'Failed to create profile.', true);
    }
  } catch (err) {
    _showFeedback(healthProfileFeedback, `Error: ${err.message}`, true);
  }
}

async function renameProfile() {
  const current = _currentConfigProfile();
  if (!current) return;
  const newName = (window.prompt('Rename profile to:', current.name) || '').trim();
  if (!newName || newName === current.name) return;
  try {
    const resp = await fetch('/api/config/health/profiles/rename', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: current.name, new_name: newName }),
    });
    const data = await resp.json();
    if (resp.ok) {
      await loadConfigProfiles(data.name);
      _showFeedback(healthProfileFeedback, `Renamed to "${data.name}".`, false);
    } else {
      _showFeedback(healthProfileFeedback, data.detail || 'Failed to rename profile.', true);
    }
  } catch (err) {
    _showFeedback(healthProfileFeedback, `Error: ${err.message}`, true);
  }
}

async function deleteProfile() {
  const current = _currentConfigProfile();
  if (!current) return;
  if (!window.confirm(`Delete profile "${current.name}"? This can't be undone.`)) return;
  try {
    const resp = await fetch(`/api/config/health/profiles?name=${encodeURIComponent(current.name)}`, {
      method: 'DELETE',
    });
    const data = await resp.json();
    if (resp.ok) {
      await loadConfigProfiles();
      _showFeedback(healthProfileFeedback, `Profile "${current.name}" deleted.`, false);
    } else {
      _showFeedback(healthProfileFeedback, data.detail || 'Failed to delete profile.', true);
    }
  } catch (err) {
    _showFeedback(healthProfileFeedback, `Error: ${err.message}`, true);
  }
}

configHealthSaveBtn.addEventListener('click', saveHealthConfig);
configProfileSelect.addEventListener('change', () => _applyProfileToPickers(_currentConfigProfile()));
document.getElementById('config-profile-new').addEventListener('click', createProfile);
document.getElementById('config-profile-rename').addEventListener('click', renameProfile);
document.getElementById('config-profile-delete').addEventListener('click', deleteProfile);

// ── Navigation (tabs) ──────────────────────────────────────────────────────

const navRca      = document.getElementById('nav-rca');
const navGithub   = document.getElementById('nav-github');
const navHealth   = document.getElementById('nav-health');
const navConfig   = document.getElementById('nav-config');
const rcaView     = document.getElementById('rca-view');
const githubView  = document.getElementById('github-view');
const healthView  = document.getElementById('health-view');
const configView  = document.getElementById('config-view');

function _activateTab(view, tab) {
  [rcaView, githubView, healthView, configView].forEach(v => v.classList.add('hidden'));
  [navRca, navGithub, navHealth, navConfig].forEach(t => t.classList.remove('active'));
  view.classList.remove('hidden');
  tab.classList.add('active');
}

function showRca() {
  _activateTab(rcaView, navRca);
}

function showGithub() {
  _activateTab(githubView, navGithub);
  if (!githubLoaded) loadGithubPullRequests();
}

async function showHealth() {
  _activateTab(healthView, navHealth);
  await loadHealthTabProfiles();
  loadServiceHealth();
}

function showConfig() {
  _activateTab(configView, navConfig);
  loadConfigPage();
}

navRca.addEventListener('click', showRca);
navGithub.addEventListener('click', showGithub);
navHealth.addEventListener('click', showHealth);
navConfig.addEventListener('click', showConfig);

// ── Init ───────────────────────────────────────────────────────────────────
loadProviders();
