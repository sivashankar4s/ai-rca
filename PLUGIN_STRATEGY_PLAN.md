# Plug-and-Play Analytics Provider — Strategy Pattern Refactoring Plan

## 1. Problem Statement

The current implementation has three hard-wired external dependencies inside `RCAOrchestrator`:

| Concern | Current class | Coupled to |
|---|---|---|
| Failure data source | `AthenaService` | Amazon Athena |
| LLM inference | `BedrockService` | Navify Enrichment API (OpenAI-compat) |
| Log / trace analytics | `CloudWatchService` | Amazon CloudWatch Logs Insights |

To support Grafana Loki, Datadog, Splunk, Elastic, or any future observability platform, all three must become **swappable at config time** — without changing orchestration logic.

---

## 2. Design: Strategy Pattern

The **Strategy Pattern** defines a family of algorithms/behaviours, encapsulates each one, and makes them interchangeable. The `RCAOrchestrator` (the *context*) holds references to abstract strategy interfaces. Concrete strategy classes (providers) are injected at startup based on configuration.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RCAOrchestrator (Context)                    │
│                                                                      │
│  self.data_source  → DataSourceStrategy (abstract)                  │
│  self.llm          → LLMStrategy        (abstract)                  │
│  self.log_backend  → LogAnalysisStrategy (abstract)                 │
└──────────────────┬──────────────────┬───────────────────────────────┘
                   │                  │
    ┌──────────────┘      ┌───────────┘
    ▼                     ▼
DataSourceStrategy     LLMStrategy          LogAnalysisStrategy
  (abstract ABC)        (abstract ABC)        (abstract ABC)
  ┌──────────────┐      ┌──────────────┐     ┌──────────────────────┐
  │ AthenaDS     │      │ NavifyLLM    │     │ CloudWatchLogBackend │
  │ LocalFileDS  │      │ OpenAILLM    │     │ GrafanaLokiBackend   │
  │ BigQueryDS * │      │ AnthropicLLM*│     │ DatadogBackend *     │
  │ ...          │      │ OllamaLLM *  │     │ ElasticBackend *     │
  └──────────────┘      └──────────────┘     │ SplunkBackend *      │
                                              └──────────────────────┘
                                               * = future provider
```

---

## 3. Target Folder Structure

```
backend/
├── strategies/                   ← NEW: abstract interfaces
│   ├── __init__.py
│   ├── data_source.py            ← DataSourceStrategy ABC
│   ├── llm.py                    ← LLMStrategy ABC
│   └── log_analysis.py           ← LogAnalysisStrategy ABC
│
├── providers/                    ← NEW: concrete implementations
│   ├── __init__.py
│   ├── data_source/
│   │   ├── __init__.py
│   │   ├── athena.py             ← AthenaDataSource  (moved from athena_service.py)
│   │   └── local_file.py         ← LocalFileDataSource
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── navify.py             ← NavifyLLMProvider (moved from bedrock_service.py)
│   │   └── openai_compat.py      ← OpenAICompatProvider (reusable base)
│   └── log_analysis/
│       ├── __init__.py
│       ├── cloudwatch.py         ← CloudWatchLogBackend (moved from cloudwatch_service.py)
│       └── grafana_loki.py       ← GrafanaLokiBackend (stub, ready to implement)
│
├── plugin_registry.py            ← NEW: factory / DI wiring
├── services/
│   ├── rca_orchestrator.py       ← UPDATED: depends on abstract strategies only
│   └── ...                       ← old *_service.py files kept during transition
├── config.py                     ← UPDATED: add ANALYTICS_PROVIDER, LLM_PROVIDER, etc.
└── models/
    └── schemas.py                ← unchanged
```

---

## 4. Abstract Strategy Interfaces

### 4.1 `DataSourceStrategy` — `backend/strategies/data_source.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class DataSourceStrategy(ABC):
    """Fetches raw failure/event records from any monitoring store."""

    @abstractmethod
    def fetch_records(
        self,
        time_range: str,
        component: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        failure_only: bool = True,
    ) -> List[Dict]:
        """Return a list of raw record dicts."""
        ...
```

### 4.2 `LLMStrategy` — `backend/strategies/llm.py`

```python
from abc import ABC, abstractmethod

class LLMStrategy(ABC):
    """Runs a text prompt against any LLM backend."""

    @abstractmethod
    def invoke(self, prompt: str, max_tokens: int = 4096) -> str:
        """Return the model's text response."""
        ...
```

### 4.3 `LogAnalysisStrategy` — `backend/strategies/log_analysis.py`

```python
from abc import ABC, abstractmethod
from typing import List

class LogAnalysisStrategy(ABC):
    """Executes a structured log query on any observability backend."""

    @abstractmethod
    def execute_query(
        self,
        query: str,
        time_range: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[str]:
        """Return a list of matching log line strings."""
        ...

    @abstractmethod
    def build_deep_link(
        self,
        region: str,
        log_group: str,
        component: str,
        time_range: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> str:
        """Return a browser-ready deep link into the observability UI."""
        ...
```

> **Why `build_deep_link` lives here?**  
> Every provider has its own URL scheme (CloudWatch console, Grafana Explore, Datadog log explorer). Keeping it on the strategy ensures the orchestrator never hard-codes a URL format.

---

## 5. Concrete Provider Implementations

### 5.1 CloudWatch (existing → adapt)

`backend/providers/log_analysis/cloudwatch.py`

- Move `CloudWatchService` logic here.
- Implement `LogAnalysisStrategy`.
- `build_deep_link` replicates the existing `_build_cw_url` helper from `rca_orchestrator.py`.

### 5.2 Grafana Loki (new stub)

`backend/providers/log_analysis/grafana_loki.py`

```python
class GrafanaLokiBackend(LogAnalysisStrategy):
    """Queries Grafana Loki via the HTTP query-range API."""

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url
        self._api_key = api_key

    def execute_query(self, query: str, time_range: str, ...) -> List[str]:
        # POST /loki/api/v1/query_range  with LogQL query
        ...

    def build_deep_link(self, ...) -> str:
        # https://<grafana-host>/explore?...
        ...
```

The LLM query-generation step must also be adapted: instead of CloudWatch Insights syntax, the LLM should generate **LogQL** for Loki or **DQL** for Datadog. This is handled by updating the prompt template inside the LLM step (see §7).

### 5.3 Navify LLM (existing → adapt)

`backend/providers/llm/navify.py` — direct lift of `BedrockService`.

### 5.4 Athena Data Source (existing → adapt)

`backend/providers/data_source/athena.py` — direct lift of `AthenaService`.

---

## 6. Plugin Registry / Factory

`backend/plugin_registry.py`

```python
from backend.config import settings
from backend.strategies.data_source import DataSourceStrategy
from backend.strategies.llm import LLMStrategy
from backend.strategies.log_analysis import LogAnalysisStrategy

def get_data_source() -> DataSourceStrategy:
    if settings.local_data_file:
        from backend.providers.data_source.local_file import LocalFileDataSource
        return LocalFileDataSource(settings.local_data_file)
    match settings.data_source_provider:          # e.g. "athena" | "bigquery"
        case "athena":
            from backend.providers.data_source.athena import AthenaDataSource
            return AthenaDataSource()
        case _:
            raise ValueError(f"Unknown data_source_provider: {settings.data_source_provider}")

def get_llm() -> LLMStrategy:
    match settings.llm_provider:                  # e.g. "navify" | "openai" | "ollama"
        case "navify" | "openai":
            from backend.providers.llm.navify import NavifyLLMProvider
            return NavifyLLMProvider()
        case _:
            raise ValueError(f"Unknown llm_provider: {settings.llm_provider}")

def get_log_backend() -> LogAnalysisStrategy:
    match settings.log_analysis_provider:         # e.g. "cloudwatch" | "grafana_loki"
        case "cloudwatch":
            from backend.providers.log_analysis.cloudwatch import CloudWatchLogBackend
            return CloudWatchLogBackend()
        case "grafana_loki":
            from backend.providers.log_analysis.grafana_loki import GrafanaLokiBackend
            return GrafanaLokiBackend(
                base_url=settings.grafana_loki_url,
                api_key=settings.grafana_api_key,
            )
        case _:
            raise ValueError(f"Unknown log_analysis_provider: {settings.log_analysis_provider}")
```

---

## 7. Updated `RCAOrchestrator`

The orchestrator becomes **provider-agnostic**. The only change is:

```python
# Before
class RCAOrchestrator:
    def __init__(self):
        self.athena    = AthenaService()
        self.cloudwatch = CloudWatchService()
        self.bedrock   = BedrockService()

# After
class RCAOrchestrator:
    def __init__(
        self,
        data_source: DataSourceStrategy,
        llm: LLMStrategy,
        log_backend: LogAnalysisStrategy,
    ):
        self.data_source = data_source
        self.llm         = llm
        self.log_backend = log_backend
```

All internal calls change from `self.athena.fetch_records(...)` → `self.data_source.fetch_records(...)`, etc.

**Query language adaptation** — the LLM prompt for generating log queries will include the provider name so the LLM generates the correct query syntax:

```python
query_language = settings.log_analysis_provider   # "cloudwatch" | "grafana_loki" | "datadog"
prompt = f"""Generate {MAX_CW_QUERIES} {query_language} log queries that surface ..."""
```

---

## 8. Config Changes (`backend/config.py`)

Add three new settings (with backward-compatible defaults):

```python
# Provider selection
data_source_provider: str = "athena"          # DATA_SOURCE_PROVIDER env var
llm_provider: str = "navify"                  # LLM_PROVIDER env var
log_analysis_provider: str = "cloudwatch"     # LOG_ANALYSIS_PROVIDER env var

# Grafana / Loki (only needed when log_analysis_provider = "grafana_loki")
grafana_loki_url: str = ""                    # GRAFANA_LOKI_URL
grafana_api_key: str = ""                     # GRAFANA_API_KEY
grafana_datasource_uid: str = ""              # GRAFANA_DATASOURCE_UID (for deep links)
```

---

## 9. Router Changes (`backend/routers/analysis.py`)

Inject strategies from the registry instead of constructing `RCAOrchestrator()` directly:

```python
from ..plugin_registry import get_data_source, get_llm, get_log_backend
from ..services.rca_orchestrator import RCAOrchestrator

def _make_orchestrator() -> RCAOrchestrator:
    return RCAOrchestrator(
        data_source=get_data_source(),
        llm=get_llm(),
        log_backend=get_log_backend(),
    )

@router.post("/failures")
async def fetch_failures(request: FailuresRequest):
    orchestrator = _make_orchestrator()
    ...
```

---

## 10. Implementation Phases

### Phase 1 — Scaffold (no functional change)
- [ ] Create `backend/strategies/` package with the three ABCs
- [ ] Create `backend/providers/` skeleton with empty `__init__.py` files
- [ ] Add `plugin_registry.py` (factory only, no logic change yet)
- [ ] Add three new provider settings to `config.py`

### Phase 2 — Migrate existing providers
- [ ] Move `AthenaService` → `AthenaDataSource(DataSourceStrategy)`
- [ ] Move `BedrockService` → `NavifyLLMProvider(LLMStrategy)`
- [ ] Move `CloudWatchService` → `CloudWatchLogBackend(LogAnalysisStrategy)` + implement `build_deep_link`
- [ ] Move `LocalFile` loading out of `AthenaService` → `LocalFileDataSource`
- [ ] Update `RCAOrchestrator` to accept injected strategies
- [ ] Update router to use `_make_orchestrator()`
- [ ] Run existing tests / manual smoke test → **no regression**

### Phase 3 — Grafana Loki provider
- [ ] Implement `GrafanaLokiBackend.execute_query` (LogQL via `/loki/api/v1/query_range`)
- [ ] Implement `GrafanaLokiBackend.build_deep_link` (Grafana Explore URL)
- [ ] Update LLM query-generation prompt to inject `query_language` variable
- [ ] Add `GRAFANA_LOKI_URL` / `GRAFANA_API_KEY` to `.env.example`
- [ ] Manual test: set `LOG_ANALYSIS_PROVIDER=grafana_loki`, verify deep links and log results

### Phase 4 — Additional providers (future)
| Provider | Strategy | Notes |
|---|---|---|
| Datadog | `LogAnalysisStrategy` | DQL queries, Datadog Logs API |
| Splunk | `LogAnalysisStrategy` | SPL queries, Splunk REST API |
| Elastic / OpenSearch | `LogAnalysisStrategy` | KQL / Lucene, REST API |
| BigQuery | `DataSourceStrategy` | Replace Athena for GCP deployments |
| Ollama / local LLM | `LLMStrategy` | Air-gapped / offline usage |

Each new provider is a single new file in `backend/providers/<type>/` — the orchestrator and router are **never touched again**.

---

## 11. Key Design Decisions

| Decision | Rationale |
|---|---|
| Use Python `ABC` (not `Protocol`) | Forces implementors to be explicit; IDE auto-complete works better for teams new to the codebase |
| Factory function (not DI framework) | Lightweight; avoids adding FastAPI DI complexity or an extra dependency like `dependency-injector` |
| Provider selection via env var at startup | Follows 12-factor app principles; no runtime switching needed |
| `build_deep_link` on the strategy | Each backend has a different URL scheme; keeps URL construction close to the provider logic |
| LLM prompt injects `query_language` | The LLM generates provider-specific syntax (CloudWatch Insights ≠ LogQL ≠ DQL) automatically |
| Old `*_service.py` files kept during Phase 1-2 | Safe incremental migration; no big-bang rewrite |

---

## 12. File Change Summary

| File | Action | Phase |
|---|---|---|
| `backend/strategies/__init__.py` | Create | 1 |
| `backend/strategies/data_source.py` | Create | 1 |
| `backend/strategies/llm.py` | Create | 1 |
| `backend/strategies/log_analysis.py` | Create | 1 |
| `backend/providers/__init__.py` | Create | 1 |
| `backend/plugin_registry.py` | Create | 1 |
| `backend/config.py` | Update (add 6 settings) | 1 |
| `backend/providers/data_source/athena.py` | Create (lift from `athena_service.py`) | 2 |
| `backend/providers/data_source/local_file.py` | Create | 2 |
| `backend/providers/llm/navify.py` | Create (lift from `bedrock_service.py`) | 2 |
| `backend/providers/log_analysis/cloudwatch.py` | Create (lift from `cloudwatch_service.py`) | 2 |
| `backend/services/rca_orchestrator.py` | Update (inject strategies) | 2 |
| `backend/routers/analysis.py` | Update (use `_make_orchestrator()`) | 2 |
| `backend/providers/log_analysis/grafana_loki.py` | Create | 3 |
| `.env.example` | Update (add new env vars) | 3 |
