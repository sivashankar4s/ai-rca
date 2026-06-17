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

// ── GitHub Integration ─────────────────────────────────────────────────────

const githubSection       = document.getElementById('github-section');
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
let currentReviewData = null;   // the last CodeReviewResult shown
let currentPrNumber = null;     // PR number for the current review (null = branch review)

function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function loadGithubPullRequests() {
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

// ── Post to PR (T009 / T015) ───────────────────────────────────────────────

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

// Kick off initial load
loadGithubPullRequests();

// ── Config Page ────────────────────────────────────────────────────────────

const MASK_SENTINEL = '••••••••';

const navAnalysis      = document.getElementById('nav-analysis');
const navConfig        = document.getElementById('nav-config');
const analysisView     = document.getElementById('analysis-view');
const configSection    = document.getElementById('config-section');

const awsStatusBadge       = document.getElementById('aws-status-badge');
const awsKeyIdInput        = document.getElementById('config-aws-key-id');
const awsSecretInput       = document.getElementById('config-aws-secret');
const awsRegionInput       = document.getElementById('config-aws-region');
const awsKeyIdError        = document.getElementById('config-aws-key-id-error');
const awsSecretError       = document.getElementById('config-aws-secret-error');
const awsSaveForm          = document.getElementById('config-aws-form');
const awsFeedback          = document.getElementById('config-aws-feedback');

const githubMcpStatusBadge = document.getElementById('github-mcp-status-badge');
const githubRepoInput      = document.getElementById('config-github-repo');
const githubTokenInput     = document.getElementById('config-github-token');
const githubBranchInput    = document.getElementById('config-github-branch');
const githubRepoError      = document.getElementById('config-github-repo-error');
const githubTokenError     = document.getElementById('config-github-token-error');
const githubMcpSaveForm    = document.getElementById('config-github-mcp-form');
const githubMcpFeedback    = document.getElementById('config-github-mcp-feedback');

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

async function loadConfigPage() {
  try {
    const resp = await fetch('/api/config');
    const data = await resp.json();

    const aws = data.aws;
    awsKeyIdInput.value    = aws.access_key_id || '';
    awsSecretInput.value   = aws.secret_access_key || '';
    awsRegionInput.value   = aws.region || '';
    _setBadge(awsStatusBadge, aws.configured);

    const github = data.github_mcp;
    githubRepoInput.value   = github.repo || '';
    githubTokenInput.value  = github.token || '';
    githubBranchInput.value = github.default_branch || '';
    _setBadge(githubMcpStatusBadge, github.configured);
  } catch (e) {
    awsFeedback.textContent = 'Failed to load configuration.';
    awsFeedback.classList.remove('hidden');
  }
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

awsSaveForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  _clearFieldError(awsKeyIdInput, awsKeyIdError);
  _clearFieldError(awsSecretInput, awsSecretError);
  awsFeedback.classList.add('hidden');

  const keyId  = awsKeyIdInput.value.trim();
  const secret = awsSecretInput.value;
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

  const isClearing = !secret || (secret !== MASK_SENTINEL && !secret.trim());
  if (isClearing) {
    if (!window.confirm('This will remove the stored Secret Access Key. Are you sure?')) return;
  }

  try {
    const resp = await fetch('/api/config/aws', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_key_id: keyId, secret_access_key: secret, region: region || undefined }),
    });
    const data = await resp.json();
    if (resp.ok && data.success) {
      _showFeedback(awsFeedback, 'AWS configuration saved.', false);
      await loadConfigPage();
    } else {
      const msg = data.detail ? JSON.stringify(data.detail) : 'Failed to save AWS configuration.';
      _showFeedback(awsFeedback, msg, true);
    }
  } catch (err) {
    _showFeedback(awsFeedback, `Error: ${err.message}`, true);
  }
});

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

  const isClearing = !token || (token !== MASK_SENTINEL && !token.trim());
  if (isClearing) {
    if (!window.confirm('This will remove the stored Personal Access Token. Are you sure?')) return;
  }

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
      const msg = data.detail ? JSON.stringify(data.detail) : 'Failed to save GitHub MCP configuration.';
      _showFeedback(githubMcpFeedback, msg, true);
    }
  } catch (err) {
    _showFeedback(githubMcpFeedback, `Error: ${err.message}`, true);
  }
});

// ── Navigation ─────────────────────────────────────────────────────────────

function showAnalysis() {
  analysisView.classList.remove('hidden');
  configSection.classList.add('hidden');
  navAnalysis.classList.add('active');
  navConfig.classList.remove('active');
}

function showConfig() {
  analysisView.classList.add('hidden');
  configSection.classList.remove('hidden');
  navConfig.classList.add('active');
  navAnalysis.classList.remove('active');
  loadConfigPage();
}

navAnalysis.addEventListener('click', showAnalysis);
navConfig.addEventListener('click', showConfig);
