# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Semantic Graph Manager — extracts entities and relationships from user-defined data folders (code, documents, etc.) using LLM-powered semantic analysis, stores them in a graph structure, and exposes querying via REST API and CLI.

## Commands

```bash
# Install (editable with dev deps)
pip install -e ".[dev]"

# Run all tests
pytest

# Run tests with coverage
pytest --cov=semantic_graph --cov-report=term-missing

# Run a single test file
pytest tests/unit/test_graph_engine.py

# Run a single test class/method
pytest tests/unit/test_graph_engine.py::TestNetworkXBackend::test_build_empty

# Lint (ruff)
ruff check src/ tests/ migrations/

# Format (ruff)
ruff format src/ tests/ migrations/

# Type check (mypy, strict mode)
mypy src/

# Run the API server
uvicorn semantic_graph.api.main:app --reload
# or via entry point:
semantic-graph-server

# CLI
semantic-graph --help
semantic-graph version

# Database migrations (targets projects.db by default)
alembic upgrade head
# Graph schema migrations
alembic -x db=graph revision --autogenerate -m "..."
alembic -x db=graph upgrade head

# Docker
docker compose up

# Pre-commit
pre-commit run --all-files
```

## Architecture

### Two-Database SQLite Storage

- **`projects.db`** (shared metadata): `Project` and `ProcessingJob` tables. Uses `ProjectsBase` declarative base.
- **Per-project `graph.db`**: `Node`, `Edge`, and `FileManifestEntry` tables. Uses `GraphBase` declarative base. Located at `~/.semantic-graph/projects/<uuid>/graph.db`.

`DatabaseManager` (`src/semantic_graph/storage/database.py`) manages both: the shared DB is created on init; per-project DBs are created lazily on first access with `get_project_engine()`. It provides `projects_session()` and `project_session(project_id)` context managers for transactional access. SQLite foreign keys are enforced via a global `Engine.connect` listener.

Alembic migrations (`migrations/`) support both databases through a `-x db=<projects|graph>` flag. The initial revision (`5ba2446fa7ea`) is target-aware — it applies the correct schema based on the `-x db=` argument.

### Graph Engine: Read/Write Separation

The graph engine is the system's core. It follows a strict read/write separation pattern:

- **Read path**: All queries are served from an in-memory `GraphBuildResult` — no SQLite round-trips. `load_graph()` in `graph_engine/graph_builder.py` reads all nodes/edges from SQLite into memory. The query layer (`graph_engine/queries.py` — `get_node`, `get_neighbors`, `get_stats`) operates against the in-memory cache.

- **Write path**: Mutations go through `GraphSyncManager` (`graph_engine/sync.py`). New nodes/edges are staged in dirty lists (invisible to readers), then flushed to both SQLite and the in-memory graph atomically on `sync()`. A per-project `threading.RLock` serializes mutations.

- **Pluggable backends**: `graph_engine/backends.py` defines a `GraphBackend` ABC with two implementations:
  - `GraphToolBackend` — high-performance via graph-tool (optional, not on PyPI)
  - `NetworkXBackend` — always-available fallback using `nx.MultiDiGraph`
  - `get_backend()` auto-selects or allows explicit selection. On import, `graph_engine/__init__.py` probes for graph-tool and sets `GRAPH_TOOL_AVAILABLE` / `GRAPH_BACKEND`.

The `GraphBuildResult` dataclass holds the backend-specific graph object plus bidirectional UUID↔index mappings, enabling backend-agnostic query code.

### Repository Pattern

`storage/repositories/` implements a generic `BaseRepository[M]` with CRUD operations plus model-specific repositories (`ProjectRepository`, `NodeRepository`, `EdgeRepository`, `FileManifestEntryRepository`, `ProcessingJobRepository`). Repositories receive sessions from the caller — they don't own sessions.

### API Layer (FastAPI)

`api/main.py` mounts routes under `/api/v1/`:
- `/api/v1/health` — health check (`api/routes/health.py`)
- `/api/v1/projects` — project management (stub)
- `/api/v1/graph` — graph queries (stub)
- `/api/v1/llm` — LLM configuration (stub)

### CLI (Typer + Rich)

`cli/main.py` defines a `typer.Typer` app with a `version` command. Entry point: `semantic-graph` (configured in `pyproject.toml`).

### Configuration

`core/config.py` uses `pydantic-settings` with `SEMANTIC_GRAPH_` env prefix. Key settings: `debug`, `api_host` (defaults to `127.0.0.1`), `api_port` (8000), `data_dir` (`~/.semantic-graph`).

### LLM Providers (stubs)

`llm/` defines `LLMProviderBase` (abstract `complete()` async method) with provider stubs for OpenAI, Anthropic, and Ollama. `LLMManager` is a stub. Pluggable provider architecture planned.

### Extractors (stubs)

`extractors/` defines `ExtractorBase` (abstract `extract()` method) with built-in stubs for code, documents, and text. `ExtractorRegistry` is a stub.

### Project State

The codebase is early-stage. Core features implemented:
- Database layer with two-DB architecture, ORM models, and repository pattern ✅
- Graph engine with pluggable backends, read/write separation, and sync manager ✅
- Health check endpoint ✅
- CLI version command ✅
- Alembic migrations for both databases ✅

Many components are stubs awaiting implementation: `ProjectManager`, `GraphManager`, API routes (projects, graph, LLM), `LLMManager`, `ExtractorRegistry`, and concrete extractors.

## GitHub Project

The project board is at https://github.com/users/hybridmachine/projects/11

## Development Conventions

- **Python**: ≥3.11
- **Linting/formatting**: ruff (double quotes, spaces); pre-commit runs ruff + trailing whitespace/YAML/TOML checks
- **Type checking**: mypy in strict mode (targeting `src/`)
- **Testing**: pytest with `asyncio_mode = "auto"`; tests organized as `tests/unit/` and `tests/integration/`; test fixtures in `tests/fixtures/`
- **Branch naming**: `<username>/<short-description>`
- **Commits**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, etc.)
- **Build**: hatchling (packages from `src/semantic_graph`)
