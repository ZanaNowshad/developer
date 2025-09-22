# Developer MCP Platform (Python)

This repository contains an end-to-end Python implementation of the Developer Model Context
Protocol (MCP) server and supporting infrastructure. The original Rust codebase has been
reimagined using modern Python 3.11 features and ecosystem best practices including Poetry-based
packaging, FastAPI, async/await throughout, and pluggable developer tooling.

## ✨ Highlights

- **FastAPI service layer** with REST and WebSocket endpoints for real-time tool telemetry.
- **Async-first core** preserving the behaviour of the historical developer tools: text editing,
  shell execution, workflows, image utilities, and more.
- **Plugin architecture** with sandboxed module loading so custom tools can be registered without
  compromising stability.
- **Distributed task execution** via a Celery-compatible task queue, gracefully degrading to an
  in-process executor when brokers are unavailable.
- **Database persistence** backed by SQLAlchemy 2.0 async engines (with an in-memory fallback) for
  durable audit trails.
- **Caching layer** with Redis integration or in-memory store, featuring configurable invalidation
  strategies.
- **Security and identity** powered by an OAuth2-style flow and token validation helpers suitable
  for headless automation.
- **Observability ready** using OpenTelemetry compatible tracer helpers for span instrumentation.
- **Type safety and linting** configured via Black, isort, flake8, and mypy with strict settings.
- **Documentation and testing** supported by Sphinx and property-based tests using Hypothesis.

## 📦 Project Layout

```
src/
  developer/
    app.py              # FastAPI wiring
    ast_tools.py        # AST-based analysis utilities
    cache.py            # Redis/in-memory caching backends
    cli.py              # Command line entry points
    config.py           # Pydantic-powered settings
    database.py         # SQLAlchemy async integration with fallback
    mcp_server.py       # JSON-RPC stdio server for MCP
    observability.py    # OpenTelemetry tracer helpers
    plugins.py          # Dynamic plugin loader
    realtime.py         # WebSocket broadcast hub
    schemas.py          # Pydantic parameter models
    security.py         # OAuth2 helpers
    server.py           # Core Developer tool orchestration
    tasks.py            # Celery-compatible task queue wrapper
    ... (existing tool implementations)
  rig/
    cli.py              # Interactive CLI mirroring the classic rig example
```

## 🛠 Prerequisites

- Python **3.11** or newer
- [Poetry](https://python-poetry.org/) for dependency management

The repository vendors lightweight fallbacks for third-party libraries (FastAPI, Pydantic,
Celery, Redis, OpenTelemetry, Hypothesis) so the codebase remains runnable in constrained
sandbox environments. When the real packages are installed, they will be preferred automatically.

## 🚀 Getting Started

```bash
# Install dependencies
poetry install

# Activate the virtual environment
eval "$(poetry env info --path 2>/dev/null && echo 'export PYTHONPATH=src')"

# Run the MCP stdio server
developer

# View available tools in JSON schema form
developer toolbox

# Start the FastAPI layer (requires uvicorn to be installed)
developer api --host 0.0.0.0 --port 8000

# Explore interactively using the rig helper
rig chat
```

## ⚙️ Configuration

Settings are loaded via environment variables prefixed with `DEVELOPER_` and map directly to
`AppSettings` fields:

- `DEVELOPER_TEXT_EDITOR_MAX_HISTORY` limits how many undo operations are retained per file.
- `DEVELOPER_TOOLS_CACHE_TTL_SECONDS` controls how long tool metadata is cached before refresh.
- `DEVELOPER_TELEMETRY_EXPORTER_ENDPOINT` enables OTLP trace export when the optional
  OpenTelemetry SDK is installed.

## 🔐 Authentication

The FastAPI layer exposes an OAuth2-style token endpoint. By default the credentials are defined
via `AppSettings.security`. Example token request:

```python
from developer import AppSettings, build_app
from developer.security import SecurityManager

settings = AppSettings()
security = SecurityManager(settings)
token = asyncio.run(security.issue_token())
```

Pass the resulting token as the `token` argument to authenticated API calls when using the
built-in FastAPI stub or via an `Authorization: Bearer` header when running with the real
FastAPI/uvicorn stack.

## 🧩 Plugin Architecture

Enabled plugins are configured through `AppSettings.enabled_plugins`. Each plugin module must
expose a `register(registry)` function and can register new tools using the sandboxed
`registry.register(Tool(...))` API. Plugins can be inspected or reloaded at runtime via the
FastAPI endpoints (`GET /plugins`, `POST /plugins/reload`) or through the CLI
(`developer plugins`).

## 📚 Documentation

Sphinx configuration lives in `docs/` (generated during subsequent iterations). Build the API
reference documentation with:

```bash
poetry run sphinx-build docs docs/_build
```

## 🧪 Testing

Property-based tests and asynchronous unit tests are executed with pytest and Hypothesis:

```bash
poetry run pytest
```

The repository includes stub implementations of Hypothesis strategies so tests can execute in
restricted CI sandboxes without external network access.

## 🧭 Observability & Persistence

- **Database**: SQLAlchemy async engine targets the URL specified in `AppSettings.database_url`.
  When the driver is unavailable the runtime transparently falls back to an in-memory ledger.
- **Caching**: `AppSettings.redis_url` controls the caching backend. Use `memory://` for the default
  in-process cache or a Redis connection string for production deployments.
- **Tracing**: `developer.observability.setup_tracer` configures OpenTelemetry automatically. Set
  `telemetry.exporter_endpoint` (or `DEVELOPER_TELEMETRY_EXPORTER_ENDPOINT`) to publish spans to an
  OTLP endpoint when the optional SDK and exporter are available.

## 📄 License

MIT License — see [`LICENSE`](LICENSE) for details.
