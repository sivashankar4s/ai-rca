# Feature Specification: Config Page Enhancements

**Feature Branch**: `019-config-page-enhancements`

**Created**: 2026-06-16

**Status**: Draft

**Input**: User description: "Config page enhancements to allow users to configure AWS credentials (client ID, secrets, access keys) and GitHub repository MCP settings through the UI"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Configure AWS Credentials (Priority: P1)

A user sets up or updates their AWS credentials directly from the application's Config page. They enter their AWS Access Key ID, AWS Secret Access Key, and optionally an AWS region/session token. The system validates the inputs and persists the credentials so they are available to downstream data-source integrations (e.g., Athena log queries).

**Why this priority**: AWS credential configuration is the most critical unblocked path — without valid credentials the data-source features are inoperable.

**Independent Test**: Can be fully tested by navigating to the Config page, entering credential values, saving, and verifying the credentials are reflected in the stored configuration without any other feature being exercised.

**Acceptance Scenarios**:

1. **Given** a user opens the Config page with no AWS credentials saved, **When** they enter a valid AWS Access Key ID and Secret Access Key and click Save, **Then** the credentials are persisted and a success confirmation is displayed.
2. **Given** a user has existing AWS credentials saved, **When** they update the values and click Save, **Then** the updated credentials replace the previous values and a success confirmation is displayed.
3. **Given** a user submits the form with the Access Key ID left blank, **When** the form is submitted, **Then** an inline validation error is shown for the required field and no save occurs.
4. **Given** a user successfully saves credentials, **When** they navigate away and return to the Config page, **Then** the saved Access Key ID is displayed (secret is masked/hidden) confirming persistence.

---

### User Story 2 - Configure GitHub Repository MCP Settings (Priority: P1)

A user specifies the GitHub repository and authentication token used by the MCP (Model Context Protocol) integration, which enables the AI-RCA tool to read repository code and raise inline PR review comments. They enter the GitHub repository URL (or owner/repo slug), the GitHub personal access token (PAT), and optionally a default branch.

**Why this priority**: MCP GitHub integration is equally critical — the inline PR comment feature (003-inline-pr-comments) depends on correct GitHub repo and token configuration being available through the UI, not just via environment variables.

**Independent Test**: Can be fully tested by entering GitHub repo settings on the Config page and verifying the saved values are loaded back without exercising any AWS-specific fields.

**Acceptance Scenarios**:

1. **Given** a user opens the Config page, **When** they enter a valid GitHub owner/repo and a personal access token and click Save, **Then** the settings are persisted and a success confirmation is displayed.
2. **Given** a user has existing GitHub MCP settings saved, **When** they change the repository slug and save, **Then** only the changed field is updated; the token field remains.
3. **Given** a user leaves the GitHub token field blank, **When** they attempt to save, **Then** an inline error indicates the token is required and no save is performed.
4. **Given** a user saves GitHub MCP settings, **When** they navigate away and return to the Config page, **Then** the repository slug is visible and the token is masked, confirming persistence.

---

### User Story 3 - Review and Validate All Configurations at a Glance (Priority: P3)

A user opens the Config page and sees a clear, organized view of all configurable integrations (AWS, GitHub MCP) with their current status (configured / not configured). They can identify which integrations are missing credentials and take action.

**Why this priority**: A status overview prevents silent misconfiguration and reduces support overhead; lower priority than actual saving because it is informational.

**Independent Test**: Can be fully tested by loading the Config page with partial configuration and verifying the status indicators are accurate without triggering any save operations.

**Acceptance Scenarios**:

1. **Given** a user has AWS credentials saved but GitHub MCP settings are missing, **When** they open the Config page, **Then** AWS shows a "Configured" status and GitHub MCP shows a "Not Configured" status.
2. **Given** all integrations are configured, **When** the user opens the Config page, **Then** all integrations show a "Configured" status with no warnings.
3. **Given** no integrations are configured, **When** the user opens the Config page, **Then** each section shows a clear "Not Configured" indicator prompting the user to fill in the details.

---

### Edge Cases

- What happens when a user pastes credentials containing leading/trailing whitespace? (System should trim and accept.)
- How does the system handle a save failure due to a backend error? (Show a user-friendly error message; do not clear entered values.)
- What happens if a user clears an existing credential field and saves? (The field should be cleared/removed from storage, with a confirmation prompt before destructive overwrite.)
- What if two browser tabs have the Config page open simultaneously and one saves? (Last-write-wins; no explicit conflict resolution required for v1.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Config page MUST present a dedicated section for AWS credential configuration, including fields for AWS Access Key ID and AWS Secret Access Key.
- **FR-002**: The Config page MUST present a dedicated section for GitHub MCP configuration, including fields for the GitHub repository (owner/repo slug) and GitHub personal access token.
- **FR-003**: All credential/token fields MUST be masked (password-style display) to prevent over-the-shoulder exposure.
- **FR-004**: The system MUST validate that all required fields in a section are non-empty before saving that section.
- **FR-005**: The system MUST persist configuration values securely so they survive browser sessions and backend restarts.
- **FR-006**: The Config page MUST display the current save status of each integration section (e.g., "Configured" vs. "Not Configured") when the page loads.
- **FR-007**: Upon a successful save, the system MUST display an explicit success confirmation to the user within the same page view.
- **FR-008**: Upon a failed save, the system MUST display a descriptive error message without clearing the user's entered values.
- **FR-009**: Saved credential identifiers (e.g., AWS Access Key ID, GitHub repo slug) MUST be readable on page load to confirm which credentials are in effect; secret values (e.g., AWS Secret, GitHub token) MUST be rendered as masked placeholders.
- **FR-010**: The system MUST allow a user to clear/remove a previously saved credential by deliberately emptying the field and saving, with a confirmation prompt before the destructive action.

### Key Entities

- **AWS Credentials**: Access Key ID (identifier), Secret Access Key (secret), optional default region. Belongs to a project or global scope.
- **GitHub MCP Settings**: Repository slug (owner/repo), personal access token (secret), optional default branch name. Belongs to a project or global scope.
- **Configuration Status**: Per-integration indicator reflecting whether required fields are present and non-empty.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can configure AWS credentials from zero to saved in under 2 minutes on the Config page.
- **SC-002**: A user can configure GitHub MCP settings from zero to saved in under 2 minutes on the Config page.
- **SC-003**: 100% of required-field validation errors are surfaced inline before any save request is sent.
- **SC-004**: The Config page correctly reflects the saved status for all integrations on every load — no stale or incorrect status indicators.
- **SC-005**: Zero plaintext secrets are visible in the rendered page or browser network traffic responses after a successful save.

## Assumptions

- The Config page already exists in the frontend; this feature adds new sections to it rather than creating a new page from scratch.
- Configuration is stored at the global (application) level for this spec; per-project configuration scoping is deferred to a future iteration (see `specs/012-multi-project-config`).
- AWS configuration covers Access Key ID and Secret Access Key as the minimum viable credential set; advanced fields (session token, role ARN) are out of scope for this iteration.
- GitHub MCP configuration covers the repository slug and a personal access token; OAuth-based GitHub authentication is out of scope for this iteration.
- Secrets are stored server-side (not in browser localStorage or cookies) and are never returned in full to the client after initial save — only a masked representation is returned.
- The backend already has a `backend/config.py` (`pydantic-settings`) pattern that this feature will extend via a configuration API endpoint rather than manual `.env` editing.
