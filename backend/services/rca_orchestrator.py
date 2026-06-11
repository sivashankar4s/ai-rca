import json
import logging
import os
from datetime import UTC, datetime

from ..config import settings
from ..models.schemas import AnalyzeResponse, FailureGroup, FailureRecord, FailuresResponse
from ..strategies.data_source import DataSourceStrategy
from ..strategies.llm import LLMStrategy
from ..strategies.log_analysis import LogAnalysisStrategy

logger = logging.getLogger(__name__)

MAX_FAILURES_TO_LLM = 50
MAX_LOG_LINES = 100
MAX_LOG_QUERIES = 3

# Per-provider query language name + syntax guidance + fallback query,
# used when prompting the LLM to generate log queries (Step 3).
_QUERY_LANGUAGE = {
    "cloudwatch": {
        "name": "Amazon CloudWatch Logs Insights",
        "guidance": (
            "  Query 1: Search by the dominant error code across all log fields — "
            "show timestamp, message, requestId\n"
            "  Query 2: Search by component name, filter for ERROR or WARN, show the "
            "full log line and any exception stack trace\n"
            "  Query 3: Correlate by file_trace_id — find all log events matching any "
            "of the sample trace IDs to show the full execution path"
        ),
        "fallback": (
            "fields @timestamp, @message | filter @message like /ERROR/ "
            "| sort @timestamp desc | limit 50"
        ),
    },
    "grafana_loki": {
        "name": "Grafana Loki LogQL",
        "guidance": (
            '  Query 1: Search by the dominant error code, e.g. `{job=~".+"} '
            '|= "<error_code>"`\n'
            '  Query 2: Search by component name, filter for ERROR or WARN, e.g. '
            '`{job=~".+"} |= "<component>" |~ "(?i)error|warn"`\n'
            '  Query 3: Correlate by file_trace_id, e.g. `{job=~".+"} |= "<trace_id>"`'
        ),
        "fallback": '{job=~".+"} |~ "(?i)error"',
    },
}


class RCAOrchestrator:
    def __init__(
        self,
        data_source: DataSourceStrategy,
        llm: LLMStrategy,
        log_backend: LogAnalysisStrategy,
    ):
        self.data_source = data_source
        self.llm = llm
        self.log_backend = log_backend

    # ------------------------------------------------------------------ #
    #  Step 1 — Fetch failures from the configured data source            #
    # ------------------------------------------------------------------ #
    def fetch_records(
        self,
        time_range: str,
        component: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        failure_only: bool = True,
    ) -> FailuresResponse:
        logger.info(
            "Fetching records  time_range=%s  start=%s  end=%s  component=%s  failure_only=%s",
            time_range, start_date, end_date, component or "<all>", failure_only,
        )
        raw = self.data_source.fetch_records(
            time_range, component, start_date=start_date, end_date=end_date, failure_only=failure_only
        )

        if raw and not settings.local_data_file:
            self._save_snapshot(raw, time_range, component)

        records = [
            FailureRecord(
                application_name=r.get("application_name"),
                component_name=r.get("component_name"),
                custom_key1=r.get("custom_key1"),
                custom_key2=r.get("custom_key2"),
                custom_key3=r.get("custom_key3"),
                event_created_timestamp=r.get("event_created_timestamp"),
                event_inserted_timestamp=r.get("event_inserted_timestamp"),
                organization=r.get("organization"),
                status=r.get("status", "FAILED"),
                event_data=r.get("event_data"),
            )
            for r in raw
        ]
        # Determine display label for time_range in the response
        display_range = f"{start_date} → {end_date}" if (start_date and end_date) else time_range
        logger.info("Returning %d failure record(s) to UI", len(records))
        return FailuresResponse(
            total=len(records),
            time_range=display_range,
            records=records,
        )

    # ------------------------------------------------------------------ #
    #  Steps 2-5 — Run RCA on user-selected records                       #
    # ------------------------------------------------------------------ #
    def analyze_records(
        self,
        time_range: str,
        records: list[FailureRecord],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> AnalyzeResponse:
        logger.info(
            "RCA started on %d selected record(s)  time_range=%s  start=%s  end=%s",
            len(records), time_range, start_date, end_date,
        )
        # Convert Pydantic models → plain dicts for the LLM helpers
        failures: list[dict] = [r.model_dump() for r in records]

        if not failures:
            display_range = f"{start_date} → {end_date}" if (start_date and end_date) else time_range
            return AnalyzeResponse(
                total_failures=0,
                time_range=display_range,
                analyzed_at=datetime.now(UTC).isoformat(),
                failure_groups=[],
                summary="No records were selected for analysis.",
            )

        logger.info("Step 2/4: Summarising failures with LLM")
        failure_summary = self._summarize_failures(failures)

        logger.info("Step 3/4: Generating %s queries", settings.log_analysis_provider)
        log_queries = self._generate_log_queries(failures, failure_summary)
        logger.info("Generated %d log query/queries", len(log_queries))

        logger.info("Step 4a/4: Executing log queries (max %d)", MAX_LOG_QUERIES)
        all_logs: list[str] = []
        for i, query in enumerate(log_queries[:MAX_LOG_QUERIES], start=1):
            logger.debug("Log query %d/%d: %s", i, MAX_LOG_QUERIES, query)
            logs = self.log_backend.execute_query(
                query, time_range, start_date=start_date, end_date=end_date
            )
            all_logs.extend(logs)
        logger.info("Collected %d total log line(s)", len(all_logs))

        logger.info("Step 4b/4: Performing RCA and grouping failures")
        groups = self._perform_rca_and_group(
            failures, failure_summary, all_logs, time_range,
            start_date=start_date, end_date=end_date,
        )
        logger.info("Identified %d failure group(s)", len(groups))

        summary = self._executive_summary(groups)

        logger.info(
            "RCA complete  total_failures=%d  groups=%d", len(failures), len(groups)
        )
        display_range = f"{start_date} → {end_date}" if (start_date and end_date) else time_range
        return AnalyzeResponse(
            total_failures=len(failures),
            time_range=display_range,
            analyzed_at=datetime.now(UTC).isoformat(),
            failure_groups=groups,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    #  Step 2 – Summarize failures                                         #
    # ------------------------------------------------------------------ #
    def _summarize_failures(self, failures: list[dict]) -> str:
        sample_count = min(len(failures), MAX_FAILURES_TO_LLM)
        logger.debug("Summarising %d/%d failure records", sample_count, len(failures))
        sample = json.dumps(failures[:MAX_FAILURES_TO_LLM], indent=2)
        prompt = f"""You are a senior platform engineer helping a developer debug pipeline failures fast.

Analyze these failure records and produce a concise, developer-focused summary covering:
1. Which component(s) are failing and what their failure rate looks like
2. The exact error codes / patterns repeating (e.g. S3_PUT_FAILED, TIMEOUT_ERROR)
3. The pipeline stage where failures cluster (e.g. lz-processor, harmonization)
4. Any time-based bursts (e.g. started at 14:00 UTC, all retries exhausted)
5. Environmental signals — device IDs, tenant aliases, or file types that appear in every failure

Failure records (JSON):
{sample}

Be specific and use the actual field values from the records. Avoid vague language.
Respond in plain text, 5-8 lines max."""
        summary = self.llm.invoke(prompt, max_tokens=1024)
        logger.debug("Failure summary (first 200 chars): %s", summary[:200])
        return summary

    # ------------------------------------------------------------------ #
    #  Step 3 – Generate log queries for the configured backend           #
    # ------------------------------------------------------------------ #
    def _generate_log_queries(self, failures: list[dict], summary: str) -> list[str]:
        trace_ids = list({f.get("custom_key1", "") for f in failures[:10] if f.get("custom_key1")})
        components = list({f.get("component_name", "") for f in failures if f.get("component_name")})
        error_codes = list({(f.get("event_data") or {}).get("error_code", "") for f in failures if (f.get("event_data") or {}).get("error_code")})
        logger.debug(
            "Generating log queries  unique_components=%s  error_codes=%s  sample_trace_ids=%s",
            components[:5], error_codes[:5], trace_ids[:5],
        )

        language = _QUERY_LANGUAGE.get(
            settings.log_analysis_provider, _QUERY_LANGUAGE["cloudwatch"]
        )

        prompt = f"""You are an expert in {language["name"]}.

A developer needs to debug pipeline failures RIGHT NOW. Generate exactly {MAX_LOG_QUERIES} {language["name"]} queries that will surface the most useful debug information quickly.

Failure context:
- Failure Summary: {summary}
- Error codes seen: {error_codes[:5]}
- Affected components: {components[:5]}
- Sample file_trace_ids: {trace_ids[:5]}

Query requirements:
{language["guidance"]}

Return ONLY a valid JSON array of {MAX_LOG_QUERIES} query strings. No explanation, no markdown.
Example: ["query1", "query2", "query3"]"""

        response = self.llm.invoke(prompt, max_tokens=768)
        queries = self._extract_json_array(response)
        if queries:
            logger.debug("LLM produced %d log query/queries", len(queries))
            return queries

        # Fallback: generic error query in the configured query language
        logger.warning("LLM did not return valid JSON for log queries — using fallback")
        return [language["fallback"]]

    # ------------------------------------------------------------------ #
    #  Steps 5 & 6 – RCA + grouping                                        #
    # ------------------------------------------------------------------ #
    def _perform_rca_and_group(
        self,
        failures: list[dict],
        summary: str,
        logs: list[str],
        time_range: str = "1h",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[FailureGroup]:
        failures_json = json.dumps(failures[:MAX_FAILURES_TO_LLM], indent=2)
        logs_text = "\n".join(logs[:MAX_LOG_LINES]) or "(no logs retrieved)"
        prompt = f"""You are a senior platform engineer performing a root cause analysis for a development team.
Your goal is to save developer time by providing immediately actionable findings — not vague advice.

Analyze the failure records and observability logs below. Group similar failures by root cause and return a JSON array.

Each object in the array MUST have these exact keys:
  - group_id          (string, unique, e.g. "grp-1")
  - component         (string, exact component_name from the records)
  - error_pattern     (string, the exact error code or short pattern, e.g. "S3_PUT_FAILED at lz-processor stage")
  - root_cause        (string, 2-3 sentences: what broke, why it broke, and what triggered it — reference actual field values)
  - failure_category  (string, one of: Database, Network, Application, Configuration, Timeout, Authentication, Resource, Unknown)
  - impact_count      (integer, number of affected records)
  - immediate_action  (string, the SINGLE most important thing a developer should do RIGHT NOW to stop the bleeding,
                       e.g. "Check IAM role arn:aws:iam::123456789:role/dp-lz-role for missing s3:PutObject on bucket dp-landing-zone-usw2")
  - likely_fix        (string, the specific code/config/infra change that will permanently fix this,
                       e.g. "Add s3:PutObject and s3:GetBucketLocation to the Lambda execution role policy and redeploy the stack")
  - affected_files    (array of strings, specific service names, Lambda functions, config files, or repos likely involved,
                       e.g. ["dp-lz-s3-event-processor", "infra/iam/dp-lz-role.tf", "config/s3-policy.json"])
  - escalation_path   (string, who to contact if the fix does not work,
                       e.g. "Escalate to AWS support if IAM propagation takes >15 min, or ping #platform-infra if role is managed by another team")
  - log_samples       (array of up to 3 actual log lines from the logs below that best illustrate the error)

IMPORTANT:
- Use actual values from the failure records (error_code, component_name, stage, device_id, custom_key1, etc.)
- Make immediate_action and likely_fix specific enough that a developer can act without needing extra context
- Do NOT write generic advice like "check the logs" or "verify configuration"

Failure Records:
{failures_json}

Failure Summary:
{summary}

Logs:
{logs_text}

Return ONLY a valid JSON array. No explanation, no markdown fences."""

        response = self.llm.invoke(prompt, max_tokens=4096)
        groups_data = self._extract_json_array(response)
        if not groups_data:
            logger.warning("LLM did not return valid JSON for failure groups — returning empty list")
            return []

        result: list[FailureGroup] = []
        for idx, g in enumerate(groups_data):
            component = g.get("component", "Unknown")
            # Attach matching failure records to this group
            group_records = [
                FailureRecord(
                    application_name=f.get("application_name"),
                    component_name=f.get("component_name"),
                    custom_key1=f.get("custom_key1"),
                    custom_key2=f.get("custom_key2"),
                    custom_key3=f.get("custom_key3"),
                    event_created_timestamp=f.get("event_created_timestamp"),
                    event_inserted_timestamp=f.get("event_inserted_timestamp"),
                    organization=f.get("organization"),
                    status=f.get("status", "FAILED"),
                    event_data=f.get("event_data"),
                )
                for f in failures
                if f.get("component_name") == component
            ][: g.get("impact_count", 5)]

            result.append(
                FailureGroup(
                    group_id=g.get("group_id", f"group_{idx}"),
                    component=component,
                    error_pattern=g.get("error_pattern", ""),
                    root_cause=g.get("root_cause", ""),
                    failure_category=g.get("failure_category", "Unknown"),
                    impact_count=g.get("impact_count", len(group_records)),
                    immediate_action=g.get("immediate_action"),
                    likely_fix=g.get("likely_fix"),
                    affected_files=g.get("affected_files", [])[:6],
                    escalation_path=g.get("escalation_path"),
                    records=group_records,
                    log_samples=g.get("log_samples", [])[:3],
                    cw_log_url=self.log_backend.build_deep_link(
                        region=settings.aws_region,
                        log_group=settings.cloudwatch_log_group,
                        component=component,
                        time_range=time_range,
                        start_date=start_date,
                        end_date=end_date,
                    ),
                )
            )
        return result

    # ------------------------------------------------------------------ #
    #  Executive summary                                                   #
    # ------------------------------------------------------------------ #
    def _executive_summary(self, groups: list[FailureGroup]) -> str:
        if not groups:
            return "No failure groups were identified."

        groups_text = "\n".join(
            f"- [{g.failure_category}] {g.component}: {g.root_cause} | "
            f"Immediate action: {g.immediate_action or 'N/A'} | "
            f"Fix: {g.likely_fix or 'N/A'} ({g.impact_count} failures)"
            for g in groups
        )
        prompt = f"""You are writing a developer-facing incident summary for an engineering team.

Based on the root cause findings below, write a 3-4 sentence summary that:
1. States which components are broken and what the error pattern is (use exact names)
2. Explains the likely root cause in plain technical language
3. Gives the most important immediate action a developer should take right now
4. Estimates the blast radius (how many records/devices/tenants are affected)

Do NOT use vague language like "there may be an issue" or "consider checking".
Write as if you are an on-call engineer handing off to the dev team.

Findings:
{groups_text}"""
        return self.llm.invoke(prompt, max_tokens=384)

    # ------------------------------------------------------------------ #
    #  Snapshot                                                            #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _save_snapshot(failures: list[dict], time_range: str, component: str | None) -> None:
        snapshots_dir = settings.snapshots_dir
        if not snapshots_dir:
            return
        try:
            os.makedirs(snapshots_dir, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            component_tag = f"_{component}" if component else ""
            filename = f"failures_{time_range}{component_tag}_{ts}.json"
            path = os.path.join(snapshots_dir, filename)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(failures, fh, indent=2)
            logger.info(
                "Saved %d failure record(s) to snapshot  file=%s",
                len(failures),
                path,
            )
        except Exception as exc:
            logger.warning("Could not save snapshot: %s", exc)

    # ------------------------------------------------------------------ #
    #  Helper                                                              #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_json_array(text: str):
        """Extract the first JSON array from an LLM response string."""
        try:
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError) as exc:
            logger.debug("JSON extraction failed: %s  raw_response_start=%s", exc, text[:120])
        return None
