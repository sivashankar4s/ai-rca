# Feature Specification: Service Health Dashboard

**Feature Branch**: `021-service-health-dashboard`

**Created**: 2026-07-06

**Status**: Draft

**Input**: User description: "Service Health Dashboard — a new top-level Health tab that shows on-demand health status for a user-configured list of AWS services: Glue jobs, Glue workflows, Lambda functions, and DataSync tasks. Config page gets a searchable multi-select picker per service. Each card shows current up/down status plus a failure count over a user-selected lookback window (1h / 24h / 7d). On-demand only — no background polling, no history, no alerting."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View health of configured services on demand (Priority: P1)

An operator opens the new **Health** tab and immediately sees, at a glance, the current status of every AWS service they have chosen to monitor (Glue jobs, Glue workflows, Lambda functions, DataSync tasks). Each service appears as a card showing whether it is currently up and how many failures it has had recently, color-coded so problems stand out.

**Why this priority**: This is the core value of the feature. Without the at-a-glance status view there is no dashboard. It is the smallest slice that delivers standalone value: an operator can answer "is anything broken right now?" in one screen.

**Independent Test**: With at least one resource of each type already configured, open the Health tab and confirm each configured resource renders a card with a current status (up/down) and a failure count, correctly color-coded.

**Acceptance Scenarios**:

1. **Given** a set of configured services with all runs healthy, **When** the operator opens the Health tab, **Then** each service shows an "up" status with zero failures and a green indicator.
2. **Given** a Glue job whose most recent run FAILED, **When** the operator opens the Health tab, **Then** that job's card shows a non-green indicator and a failure count of at least 1.
3. **Given** a Lambda function that is currently disabled/inactive, **When** the operator opens the Health tab, **Then** that function's card shows a "down" status with a red indicator.
4. **Given** a service that cannot be reached or whose status cannot be determined, **When** the operator opens the Health tab, **Then** that service's card shows an "unknown" state with an explanatory detail rather than a false "up" or "down".

---

### User Story 2 - Choose the failure lookback window (Priority: P2)

The operator adjusts the failure lookback window (e.g. last 1 hour, last 24 hours, last 7 days) on the Health tab and the failure counts recompute for that window so they can distinguish a one-off blip from a sustained problem.

**Why this priority**: Meaningfully increases diagnostic value but the dashboard is still useful with a single default window, so it ranks below the core view.

**Independent Test**: Configure a service with failures spread across time, change the window control between 1h / 24h / 7d, and confirm the failure count for that service changes to reflect only failures within the selected window.

**Acceptance Scenarios**:

1. **Given** a service with 1 failure in the last hour and 5 in the last 7 days, **When** the operator selects the "1h" window, **Then** the card shows a failure count of 1.
2. **Given** the same service, **When** the operator selects the "7d" window, **Then** the card shows a failure count of 5.
3. **Given** any selected window, **When** the operator changes it, **Then** all service cards recompute against the new window without requiring a page reload.

---

### User Story 3 - Configure which resources are monitored (Priority: P1)

On the Config page, the operator searches and multi-selects specific Glue jobs, Glue workflows, Lambda functions, and DataSync tasks from lists discovered in their AWS account, and saves the selection. Only the selected resources appear on the Health tab.

**Why this priority**: The dashboard cannot show anything meaningful until the operator has told it which resources to watch. It is a hard prerequisite for User Story 1, so it is also P1.

**Independent Test**: On the Config page, open each service picker, search for a known resource name, select one or more, save, and confirm the selection persists across a reload and that exactly those resources appear on the Health tab.

**Acceptance Scenarios**:

1. **Given** valid AWS credentials, **When** the operator opens a service picker, **Then** the picker lists resource names discovered from the AWS account and supports type-to-filter search.
2. **Given** a picker with many results, **When** the operator selects several resources and saves, **Then** those selections persist and are reflected on the Health tab.
3. **Given** no resources are selected for a given service type, **When** the operator opens the Health tab, **Then** that service type contributes no cards (and the tab does not error).

---

### Edge Cases

- **No resources configured at all**: the Health tab shows an empty state prompting the operator to configure services on the Config page, not an error.
- **AWS credentials missing or invalid**: the tab surfaces a clear message that health cannot be retrieved and why, rather than silently showing everything as "up".
- **A configured resource no longer exists** (deleted in AWS since selection): its card shows an "unknown"/"not found" state and does not block the other cards from rendering.
- **A resource has never run** (e.g. a brand-new Glue job with no run history): current status reflects "no runs yet" and failure count is zero rather than "down".
- **Partial failure of a fan-out**: if one service type's lookup fails, the other service types still render their results; the failing type is marked "unknown" with a reason.
- **Slow lookups**: the operator gets feedback that checks are in progress and can still read results as they complete or after a bounded wait.
- **Refresh during in-flight checks**: pressing Refresh while a check is running does not produce duplicate or inconsistent cards.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a new top-level "Health" view, separate from existing views, dedicated to service health.
- **FR-002**: The system MUST allow the operator to configure, per service type (Glue jobs, Glue workflows, Lambda functions, DataSync tasks), which specific resources are monitored, chosen from resources discovered in the connected AWS account.
- **FR-003**: Each service picker MUST support type-to-filter search and selection of multiple resources, and MUST persist selections so they survive a reload.
- **FR-004**: The Health view MUST display one card per configured resource, grouped or labeled by service type.
- **FR-005**: Each card MUST show the resource's current status as one of: up, down, or unknown.
- **FR-006**: Each card MUST show a count of failures over the currently selected lookback window.
- **FR-007**: Each card MUST be color-coded: green = up with zero failures in window; amber = up with one or more failures in window; red = down; a distinct neutral indicator = unknown.
- **FR-008**: The Health view MUST offer a lookback-window control with at least the options 1 hour, 24 hours, and 7 days, and MUST recompute failure counts when the window changes.
- **FR-009**: The Health view MUST provide a Refresh action that re-runs all checks on demand and updates the cards.
- **FR-010**: The system MUST determine current status and failure counts using the following per-service semantics:
  - Lambda: current = function is Active; failures = count of invocation errors over the window.
  - Glue job: current = most recent run is not in a failed/stuck state; failures = count of runs that failed/timed out/errored within the window.
  - Glue workflow: current = most recent workflow run is not in a failed state; failures = count of workflow runs that failed within the window.
  - DataSync task: current = task is available; failures = count of task executions that errored within the window.
- **FR-011**: The system MUST resolve AWS credentials from the same single source used elsewhere in the application (stored account configuration first, environment fallback, never mixed).
- **FR-012**: The system MUST degrade gracefully: if a particular resource or an entire service type cannot be evaluated, it MUST be marked "unknown" with an explanatory detail while all other results still render.
- **FR-013**: The system MUST perform health checks only on demand (on view load and on Refresh). It MUST NOT run background polling, store health history, or send alerts.
- **FR-014**: The system MUST show a clear empty state when no resources are configured, and a clear error state when AWS credentials are missing or invalid.

### Key Entities *(include if feature involves data)*

- **Monitored Resource Selection**: the operator's saved choice of which resources to watch, per service type. Attributes: service type, list of resource identifiers. Persisted with the rest of the application configuration.
- **Service Health Result**: the computed health of one resource at check time. Attributes: service type, resource name/identifier, current status (up/down/unknown), failure count for the selected window, last-run/last-activity timestamp (when available), and a human-readable detail (e.g. reason for down/unknown). Transient — not persisted.
- **Lookback Window**: the operator-selected time range (e.g. 1h / 24h / 7d) that scopes failure counting. A view-level setting, not persisted as history.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator with services already configured can determine whether any monitored service is currently unhealthy within 10 seconds of opening the Health tab, without navigating elsewhere.
- **SC-002**: 100% of configured resources appear as a card with a definite state (up, down, or unknown) — no configured resource is silently omitted.
- **SC-003**: A failure that occurred within the selected lookback window is reflected in the corresponding card's failure count in 100% of cases; failures outside the window are never counted.
- **SC-004**: Changing the lookback window updates all affected failure counts without a full page reload.
- **SC-005**: When one service type cannot be evaluated, at least all other service types still render their results (no all-or-nothing failure of the dashboard).
- **SC-006**: An operator can go from an empty configuration to seeing a monitored resource's health on the Health tab in under 2 minutes (discover → select → save → view).

## Assumptions

- AWS credentials are already available to the application (via stored account configuration or environment), reusing the existing credential-resolution mechanism; this feature adds no new credential-entry flow.
- The AWS principal in use has read/list permissions for the relevant services (Glue, Lambda, DataSync) and for the metrics needed to count Lambda invocation errors. Missing permissions surface as an "unknown"/error state rather than a crash.
- "Database" health is explicitly out of scope for this feature.
- On-demand only: no scheduler, no persistence of health results, and no notification/alerting are in scope for this version.
- The lookback window is a view-level control with fixed preset options (1h / 24h / 7d); arbitrary custom ranges are out of scope for this version.
- The failure lookback window applies uniformly to all services on the tab (one window at a time, not per-card).
- Resource discovery for the pickers follows the same interaction pattern as the existing CloudWatch log-group picker (searchable multi-select populated from AWS list operations).
- A single combined retrieval powers the tab so the operator sees all service types together on one screen.
