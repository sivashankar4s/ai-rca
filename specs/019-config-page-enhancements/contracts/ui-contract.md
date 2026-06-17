# UI Contract: Config Page

**File**: `frontend/index.html` (markup) + `frontend/app.js` (behaviour) + `frontend/style.css` (styles)

---

## Navigation

A new "Config" tab is added to the existing top-level navigation (matching the style of existing tabs/sections). Clicking it shows the `#config-section` and hides all other sections.

---

## Page Structure

```
#config-section
├── h2 "Configuration"
├── #config-aws-card  (AWS Credentials card)
│   ├── h3 "AWS Credentials"
│   ├── .config-status-badge  (shows "Configured" or "Not Configured")
│   ├── form#config-aws-form
│   │   ├── label + input#config-aws-key-id        (type="text", required)
│   │   ├── label + input#config-aws-secret        (type="password", required)
│   │   ├── label + input#config-aws-region        (type="text", optional, placeholder="us-east-1")
│   │   └── button#config-aws-save  "Save AWS Config"
│   └── .config-feedback  (success/error message area)
│
└── #config-github-mcp-card  (GitHub MCP Settings card)
    ├── h3 "GitHub MCP Settings"
    ├── .config-status-badge
    ├── form#config-github-mcp-form
    │   ├── label + input#config-github-repo       (type="text", required, placeholder="owner/repo")
    │   ├── label + input#config-github-token      (type="password", required)
    │   └── label + input#config-github-branch     (type="text", optional, placeholder="main")
    └── .config-feedback
```

---

## Behaviour Contract

### On page load (`DOMContentLoaded` or tab activation)
1. Call `GET /api/config`
2. For each integration section:
   - If `configured: true`: populate read-only identifier fields (key ID, repo slug) and set secret fields to `"••••••••"`; set badge to "Configured"
   - If `configured: false`: leave all fields empty; set badge to "Not Configured"

### On Save (per section)
1. Collect field values from the form
2. If any required field is empty (after trimming): show inline error under that field; abort fetch
3. POST `PATCH /api/config/aws` or `PATCH /api/config/github-mcp` with JSON body
4. On success (200): display success message in `.config-feedback`; re-run page load to refresh status badges
5. On error (4xx/5xx): display error message from response in `.config-feedback`; do NOT clear field values

### Mask Sentinel Handling
- When the secret field already contains `"••••••••"` (loaded from GET) and the user has not modified it, send the mask value as-is — the backend recognises it as "no-change"
- When the user edits the secret field (the value differs from `"••••••••"`), send the new value

### Clear / Remove
- Emptying a credential field and saving triggers a confirmation dialog (`window.confirm`) before the PATCH is sent: "This will remove the stored [credential name]. Are you sure?"
- If confirmed, send the PATCH with the empty value; the backend stores null/empty, effectively removing the credential

---

## CSS / Styling Contract

- All new styles use existing CSS custom properties from `style.css` (e.g., `--color-primary`, `--color-error`, `--spacing-*`) — no ad-hoc hex/px values
- `.config-status-badge` variants: `--configured` (green accent) and `--not-configured` (grey/warning)
- Card layout matches existing `.card` or panel pattern already in `style.css`
- Secret inputs styled identically to other password fields in the app — no special treatment
- Feedback messages use the existing `.error` / `.success` classes if already defined, or new classes following the same naming pattern

---

## Accessibility

- All form inputs have associated `<label>` elements (via `for`/`id` pairing)
- Save buttons use `type="submit"` on the `<form>` element (not bare `<button onclick>`)
- Event listeners attached via `addEventListener` — no inline `onclick` attributes (per constitution)
- Status badges include a text label (not icon-only) for screen reader compatibility
