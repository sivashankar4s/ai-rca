import json
import logging
import urllib.parse
from datetime import UTC, datetime, timedelta

import requests

from ...strategies.log_analysis import LogAnalysisStrategy

logger = logging.getLogger(__name__)

QUERY_TIMEOUT = 30
RANGE_SECONDS = {"1h": 3600, "1d": 86400, "1w": 604800}


class GrafanaLokiBackend(LogAnalysisStrategy):
    """Queries Grafana Loki via the HTTP query-range API (through the Grafana datasource proxy)."""

    def __init__(self, base_url: str, api_key: str, datasource_uid: str = ""):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._datasource_uid = datasource_uid

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _time_range_ns(
        self, time_range: str, start_date: str | None, end_date: str | None
    ) -> tuple[int, int]:
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=UTC)
            end_dt = datetime.fromisoformat(end_date).replace(tzinfo=UTC)
        else:
            delta = timedelta(seconds=RANGE_SECONDS.get(time_range, 3600))
            end_dt = datetime.now(UTC)
            start_dt = end_dt - delta
        return int(start_dt.timestamp() * 1e9), int(end_dt.timestamp() * 1e9)

    def execute_query(
        self,
        query: str,
        time_range: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        start_ns, end_ns = self._time_range_ns(time_range, start_date, end_date)
        url = f"{self._base_url}/api/datasources/proxy/uid/{self._datasource_uid}/loki/api/v1/query_range"

        logger.info("Querying Grafana Loki  url=%s  query=%s", url, query)
        try:
            resp = requests.get(
                url,
                headers=self._headers(),
                params={
                    "query": query,
                    "start": start_ns,
                    "end": end_ns,
                    "limit": 50,
                    "direction": "backward",
                },
                timeout=QUERY_TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
        except requests.exceptions.RequestException as exc:
            logger.error("Grafana Loki query error: %s", exc, exc_info=True)
            return [f"[Grafana Loki query error: {exc}]"]

        results = payload.get("data", {}).get("result", [])
        lines: list[tuple[int, str]] = []
        for stream in results:
            labels = stream.get("stream", {})
            label_str = " | ".join(f"{k}={v}" for k, v in labels.items())
            for ts_ns, line in stream.get("values", []):
                prefix = f"{label_str} | " if label_str else ""
                lines.append((int(ts_ns), f"{prefix}{line}"))

        lines.sort(key=lambda item: item[0], reverse=True)
        formatted = [line for _, line in lines[:50]]
        logger.info("Grafana Loki query returned %d line(s)", len(formatted))
        return formatted

    def build_deep_link(
        self,
        region: str,
        log_group: str,
        component: str,
        time_range: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> str:
        """Build a Grafana Explore deep-link scoped to the given component."""
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=UTC)
            end_dt = datetime.fromisoformat(end_date).replace(tzinfo=UTC)
        else:
            delta = timedelta(seconds=RANGE_SECONDS.get(time_range, 3600))
            end_dt = datetime.now(UTC)
            start_dt = end_dt - delta

        from_ms = int(start_dt.timestamp() * 1000)
        to_ms = int(end_dt.timestamp() * 1000)

        logql = f'{{job=~".+"}} |= `{component}`'
        if log_group:
            logql = f'{{job="{log_group}"}} |= `{component}`'

        explore_state = {
            "datasource": self._datasource_uid,
            "queries": [{"refId": "A", "expr": logql, "datasource": {"uid": self._datasource_uid}}],
            "range": {"from": str(from_ms), "to": str(to_ms)},
        }
        encoded = urllib.parse.quote(json.dumps(explore_state), safe="")
        return f"{self._base_url}/explore?orgId=1&left={encoded}"
