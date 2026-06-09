# Semantic Graph Manager — Developer Guide

## 1. Project Overview

Semantic Graph Manager extracts entities and relationships from user-defined data folders (code, documents, etc.) using LLM-powered semantic analysis, stores them in a graph structure, and exposes querying via REST API and CLI.

- **Language**: Python ≥ 3.11
- **Build system**: hatchling
- **License**: MIT
- **Repository**: `https://github.com/hybridmachine/semantic-graph`
- **Project board**: `https://github.com/users/hybridmachine/projects/11`

---

## 2. Architecture

### 2.1 High-Level Design

```
┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
│   CLI App   │  │  REST API   │  │    Extractors    │
│  (Typer)    │  │  (FastAPI)  │  │  (LLM-powered)   │
└──────┬──────┘  └──────┬──────┘  └────────┬────────┘
       │                │                  │
       └────────────────┼──────────────────┘
                        │
               ┌────────┴────────┐
               │   Core Layer    │
               │  (Managers)     │
               └────────┬────────┘
                        │
       ┌────────────────┼──────────────────┐
       │                │                  │
┌──────┴──────┐  ┌──────┴──────┐  ┌───────┴───────┐
│  Graph      │  │   Storage   │  │   LLM         │
│  Engine     │  │   Layer     │  │   Providers   │
└─────────────┘  └─────────────┘  └───────────────┘
```

### 2.2 Two-Database SQLite Architecture

The system uses two separate SQLite databases:

| Database | Purpose | Location |
|----------|---------|----------|
| `projects.db` | Shared metadata: projects, processing jobs | `~/.semantic-graph/projects.db` |
| `graph.db` | Per-project: nodes, edges, file manifests | `~/.semantic-graph/projects/<uuid>/graph.db` |

This separation keeps project metadata lightweight and queryable independently of per-project graph data.

**Declarative bases**: `ProjectsBase` and `GraphBase` are separate — each database's tables are created via its own metadata instance. Foreign keys are enforced globally via a `PRAGMA foreign_keys=ON` listener on every SQLite connection.

### 2.3 Graph Engine: Read/Write Separation

The graph engine is the system's core. It enforces a strict read/write separation:

- **Read path**: All queries are served from an in-memory `GraphBuildResult` — no SQLite round-trips. `load_graph()` reads all nodes/edges from SQLite into memory.
- **Write path**: Mutations go through `GraphSyncManager`. New nodes/edges are staged in dirty lists (invisible to readers), then flushed to both SQLite and the in-memory graph atomically on `sync()`.
- **Single-writer lock**: A per-project `threading.RLock` serializes mutations.

### 2.4 Pluggable Graph Backends

The graph engine supports two backends via a `GraphBackend` ABC:

| Backend | Availability | Use Case |
|---------|-------------|----------|
| `NetworkXBackend` | Always available (via `networkx` pip package) | Development, testing, small-to-medium graphs |
| `GraphToolBackend` | Optional (via system `python3-graph-tool`) | Production, high-performance, large graphs |

`get_backend()` auto-selects graph-tool if installed, otherwise falls back to NetworkX. You can force a specific backend with `get_backend("networkx")` or `get_backend("graph-tool")`.

### 2.5 Repository Pattern

`storage/repositories/` implements a generic `BaseRepository[M]` with CRUD operations plus model-specific repositories (`ProjectRepository`, `NodeRepository`, `EdgeRepository`, `FileManifestEntryRepository`, `ProcessingJobRepository`). Repositories receive sessions from the caller — they don't own sessions.

---

## 3. Directory Structure

```
.
├── .github/workflows/ci.yml      # CI pipeline (lint, typecheck, test)
├── .pre-commit-config.yaml        # Pre-commit hooks (ruff, whitespace, YAML/TOML)
├── alembic.ini                    # Alembic configuration
├── configs/                       # Runtime configuration files (future use)
├── docker-compose.yml             # Docker Compose setup
├── Dockerfile                     # Multi-stage Docker build
├── docs/                          # Documentation (including this guide)
├── migrations/                    # Alembic migrations
│   ├── env.py                     # Migration environment (two-DB aware)
│   ├── script.py.mako             # Migration template
│   └── versions/
│       └── 5ba2446fa7ea_initial_schema.py
├── pyproject.toml                 # Project metadata, deps, tool config
├── requirements.txt               # Pinned production dependencies
├── requirements-dev.txt           # Pinned dev dependencies
├── REQUIREMENTS.md                # Requirements specification document
├── src/semantic_graph/            # Application source
│   ├── __init__.py                # Version: 0.1.0
│   ├── api/                       # FastAPI REST API
│   │   ├── main.py                # App creation, middleware, routers
│   │   ├── middleware/            # Error handler, request logging
│   │   ├── routes/                # health, projects, graph, llm
│   │   └── schemas/               # Pydantic request/response models
│   ├── cli/                       # Typer CLI
│   │   ├── main.py                # App root: version, project, config subcommands
│   │   ├── commands/              # Subcommand groups
│   │   └── formatters/            # Output formatting utilities
│   ├── core/                      # Business logic
│   │   ├── config.py              # Settings (pydantic-settings)
│   │   ├── project_manager.py     # Project CRUD & lifecycle
│   │   └── graph_manager.py       # Graph operations (stub)
│   ├── extractors/                # File extraction system
│   │   ├── base.py                # ExtractorBase ABC
│   │   ├── registry.py            # ExtractorRegistry (stub)
│   │   ├── scanner.py             # File system scanner with filtering
│   │   └── builtins/              # Built-in extractors (code, docs, text)
│   ├── graph_engine/              # In-memory graph engine
│   │   ├── __init__.py            # Backend probe, public API exports
│   │   ├── backends.py            # GraphBackend ABC, NetworkX, graph-tool
│   │   ├── graph_builder.py       # load_graph — SQLite → memory
│   │   ├── queries.py             # get_node, get_neighbors, get_stats
│   │   └── sync.py                # GraphSyncManager — deferred writes
│   ├── llm/                       # LLM provider abstraction
│   │   ├── provider_base.py       # LLMProviderBase ABC
│   │   ├── manager.py             # LLMManager (stub)
│   │   ├── prompts/               # Prompt templates
│   │   └── providers/             # OpenAI, Anthropic, Ollama stubs
│   ├── storage/                   # Database layer
│   │   ├── database.py            # DatabaseManager
│   │   ├── models.py              # ORM models (Project, Node, Edge, etc.)
│   │   └── repositories/          # Repository pattern (BaseRepository + specific)
│   └── utils/                     # Shared utilities
│       ├── errors.py              # Exception hierarchy
│       ├── helpers.py             # General helpers
│       ├── logging.py             # Logging setup
│       └── security.py            # Path validation, binary detection
└── tests/                         # Test suite
    ├── fixtures/                  # Shared test fixtures
    ├── integration/               # Integration tests
    └── unit/                      # Unit tests (10 test files)
```

---

## 4. Key Subsystems

### 4.1 Storage Layer (`storage/`)

**DatabaseManager** (`database.py`): Manages connections to both databases. Creates `projects.db` on init; per-project `graph.db` files are created lazily on first access with `get_project_engine()`. Provides `projects_session()` and `project_session(project_id)` context managers for transactional access.

**Models** (`models.py`): Six ORM models across two declarative bases:

| Model | Database | Purpose |
|-------|----------|---------|
| `Project` | projects.db | Project configuration, scan settings, LLM config |
| `ProcessingJob` | projects.db | Tracks async file processing jobs |
| `Node` | graph.db | Semantic graph nodes with name, type, abstraction level |
| `Edge` | graph.db | Directed relationships between nodes with confidence score |
| `FileManifestEntry` | graph.db | Per-file processing state and content hashes |

Key fields:
- `Node`: `id`, `project_id`, `name`, `type`, `abstraction_level` (fine/mid/high), `source_file`, `content_snippet`, `metadata_`
- `Edge`: `id`, `project_id`, `source_node_id`, `target_node_id`, `relationship_type`, `confidence_score`, `metadata_`
- `Project`: `id`, `name` (unique), `root_path`, `include_patterns`/`exclude_patterns`, `respect_gitignore`, `max_file_size_bytes`, `llm_provider`/`llm_model`/`llm_parameters`, `status`

**Repositories** (`repositories/`): `BaseRepository[M]` provides `create()`, `get_by_id()`, `list_all()`, `update()`, `delete()`. Model-specific repositories extend it with domain queries (e.g., `ProjectRepository.get_by_name()`, `FileManifestEntryRepository.list_by_project()`).

### 4.2 Graph Engine (`graph_engine/`)

**GraphBuildResult** (`backends.py`): A dataclass holding the backend-specific graph object (`_graph`) plus bidirectional UUID↔index mappings (`_node_id_to_idx`, `_idx_to_node_id`). Also stores side-dicts for node and edge attributes, enabling uniform access across backends.

**GraphBackend ABC** (`backends.py`): Abstract interface with build/query/mutate methods:
- `build(nodes, edges) → GraphBuildResult`
- `get_node_attrs()`, `get_neighbor_indices()`, `get_edge_attrs()`
- `node_count()`, `edge_count()`
- `add_node()`, `add_edge()`

**load_graph()** (`graph_builder.py`): The single read-from-SQLite entry point. Reads all `Node` and `Edge` rows for a project and feeds them to `backend.build()`.

**Query functions** (`queries.py`): `get_node()`, `get_neighbors()` (with direction: out/in/all), `get_stats()` — all operate against an in-memory `GraphBuildResult`.

**GraphSyncManager** (`sync.py`): The write path. Stage nodes/edges via `add_node()`/`add_edge()`, then persist everything to both SQLite and the in-memory graph atomically with `sync()`. Key properties:
- `build_result` — the committed graph (does NOT include staged changes)
- `dirty_node_count` / `dirty_edge_count` — count of pending changes
- `sync()` returns the number of rows written
- `shutdown()` syncs remaining changes (call during teardown)
- `write_lock()` context manager for explicit lock acquisition

### 4.3 API Layer (`api/`)

**main.py**: Creates the FastAPI app, mounts CORS middleware (origins from config), request logging middleware, global exception handler (converts `SemanticGraphError` subclasses to structured JSON), and includes routers under `/api/v1/`.

**Routes**:
| Route | Methods | Purpose |
|-------|---------|---------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/version` | GET | API version |
| `/api/v1/projects` | GET, POST | List and create projects |
| `/api/v1/projects/{id}` | GET, PUT, DELETE | Project CRUD |
| `/api/v1/projects/{id}/scan` | POST | Trigger file scan |
| `/api/v1/projects/{id}/files` | GET | List file manifest entries |
| `/api/v1/graph` | — | Graph queries (stub) |
| `/api/v1/llm` | — | LLM configuration (stub) |

The API uses module-level singletons for `DatabaseManager`, `ProjectManager`, and `FileManifestEntryRepository`.

### 4.4 CLI (`cli/`)

**main.py**: Typer app with subcommand groups:
- `semantic-graph version` — print version
- `semantic-graph project <subcommand>` — project management
- `semantic-graph config <subcommand>` — configuration

Built with Rich for formatted terminal output.

### 4.5 Core (`core/`)

**Settings** (`config.py`): pydantic-settings with `SEMANTIC_GRAPH_` env prefix.

| Setting | Default | Description |
|---------|---------|-------------|
| `app_name` | `semantic-graph` | Application name |
| `debug` | `false` | Debug mode |
| `api_host` | `127.0.0.1` | API listen address (use `0.0.0.0` for Docker) |
| `api_port` | `8000` | API listen port |
| `data_dir` | `~/.semantic-graph` | Data directory for SQLite databases |
| `cors_origins` | `["http://localhost:3000", "http://127.0.0.1:3000"]` | Allowed CORS origins |

**ProjectManager** (`project_manager.py`): Business logic for project CRUD. Validates root paths via `validate_project_root()`, enforces name uniqueness, handles cleanup of per-project `graph.db` directories on delete.

### 4.6 File Scanner (`extractors/scanner.py`)

`FileScanner` recursively walks a project root and filters files using:
- Default exclude patterns (`.git`, `node_modules`, `.venv`, `__pycache__`, `dist`, `build`)
- User-configured include/exclude glob patterns
- `.gitignore` support (with negation via `!`)
- File size limit (default 10 MB)
- Binary file detection (null byte check)
- Symlink safety (resolved targets checked for path traversal)

Returns a `ScanReport` with `included`, `skipped`, and `errors` lists. `build_manifest_entry()` converts `FileScanResult` to `FileManifestEntry` for database storage.

### 4.7 Path Security (`utils/security.py`)

Security functions used by the scanner and API layers:
- `canonicalize_path()` — resolve to absolute canonical form
- `is_within_root()` — path traversal check
- `validate_safe_path()` — combined canonicalize + within-root check
- `validate_project_root()` — existence, directory, and protected-system-directory check
- `is_binary_file()` — null byte detection in first 8KB

### 4.8 Exception Hierarchy (`utils/errors.py`)

```
SemanticGraphError (base)
├── ProjectNotFoundError
├── GraphEngineError
├── LLMProviderError
├── PathTraversalError
├── PathSecurityError
└── ValidationError
```

---

## 5. Development Setup

### 5.1 Prerequisites

- Python ≥ 3.11
- (Optional) graph-tool for the high-performance backend: `apt install python3-graph-tool` (Debian/Ubuntu) or see [installation instructions](https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions)

### 5.2 Install

```bash
# Clone the repository
git clone https://github.com/hybridmachine/semantic-graph.git
cd semantic-graph

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks
pre-commit install
```

### 5.3 Environment Variables

Settings are loaded with the `SEMANTIC_GRAPH_` prefix. Common overrides:

```bash
export SEMANTIC_GRAPH_DEBUG=true
export SEMANTIC_GRAPH_API_HOST=0.0.0.0
export SEMANTIC_GRAPH_API_PORT=8000
export SEMANTIC_GRAPH_DATA_DIR=/path/to/data
```

Or create a `.env` file in the project root (loaded automatically by pydantic-settings).

---

## 6. Running Tests

### 6.1 Test Organization

```
tests/
├── unit/
│   ├── test_api_smoke.py        # API endpoint existence checks
│   ├── test_cli_commands.py     # CLI command integration tests
│   ├── test_cli_smoke.py        # CLI app structure checks
│   ├── test_database.py         # DatabaseManager tests
│   ├── test_graph_engine.py     # Backends, builder, queries, sync, concurrency
│   ├── test_models.py           # ORM model tests
│   ├── test_project_api.py      # Project API endpoint tests
│   ├── test_repositories.py     # Repository pattern tests
│   ├── test_scanner.py          # FileScanner tests
│   └── test_security.py         # Path security tests
├── integration/                 # Integration tests (future)
└── fixtures/                    # Shared test fixtures
```

### 6.2 Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=semantic_graph --cov-report=term-missing

# Run a single test file
pytest tests/unit/test_graph_engine.py

# Run a single test class
pytest tests/unit/test_graph_engine.py::TestNetworkXBackend

# Run a single test method
pytest tests/unit/test_graph_engine.py::TestNetworkXBackend::test_build_empty

# Run with verbose output
pytest -v

# Run with specific markers (when available)
pytest -m "slow"
```

### 6.3 Test Configuration

`pyproject.toml` configures pytest:
- `testpaths = ["tests"]`
- `asyncio_mode = "auto"` — async test functions are automatically run in an event loop
- Coverage configured with `branch = true` and `show_missing = true`

---

## 7. Interacting with the System

### 7.1 CLI

```bash
# Show help
semantic-graph --help

# Show version
semantic-graph version

# Project management
semantic-graph project --help
semantic-graph project list
semantic-graph project create --name "my-project" --root-path /path/to/code
semantic-graph project show <project-id>
semantic-graph project delete <project-id>

# Configuration
semantic-graph config --help
```

### 7.2 REST API

```bash
# Start the API server
semantic-graph-server
# Or directly:
uvicorn semantic_graph.api.main:app --reload

# Health check
curl http://127.0.0.1:8000/api/v1/health
# → {"status": "ok"}

# Version
curl http://127.0.0.1:8000/api/v1/version
# → {"status": "ok", "message": "semantic-graph v0.1.0"}

# Create a project
curl -X POST http://127.0.0.1:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-project",
    "root_path": "/path/to/code",
    "include_patterns": ["*.py", "*.md"],
    "exclude_patterns": ["**/test/**"],
    "respect_gitignore": true
  }'

# List projects
curl http://127.0.0.1:8000/api/v1/projects

# Get project details
curl http://127.0.0.1:8000/api/v1/projects/<project-id>

# Update project
curl -X PUT http://127.0.0.1:8000/api/v1/projects/<project-id> \
  -H "Content-Type: application/json" \
  -d '{"name": "renamed-project"}'

# Delete project
curl -X DELETE http://127.0.0.1:8000/api/v1/projects/<project-id>

# Trigger scan (async, stub)
curl -X POST http://127.0.0.1:8000/api/v1/projects/<project-id>/scan \
  -H "Content-Type: application/json" \
  -d '{"mode": "full"}'

# List project files
curl http://127.0.0.1:8000/api/v1/projects/<project-id>/files
```

### 7.3 Interactive API Docs

When the server is running, FastAPI provides automatic interactive docs:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## 8. Docker

### 8.1 Build and Run

```bash
# Build and start
docker compose up --build

# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### 8.2 Docker Architecture

The Dockerfile uses a multi-stage build:
1. **Builder stage** (`python:3.11-slim`): Installs hatchling, copies dependency files, installs the package
2. **Runtime stage** (`python:3.11-slim`): Installs graph-tool from Debian repo, creates non-root `semanticgraph` user, copies installed packages from builder

The container:
- Exposes port `8000`
- Runs as non-root user `semanticgraph`
- Stores data in `/data` (mounted as a named volume `semantic_graph_data`)
- Sets `SEMANTIC_GRAPH_API_HOST=0.0.0.0` (needed for Docker networking)
- Includes a `HEALTHCHECK` against `/api/v1/health`

### 8.3 docker-compose.yml

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - semantic_graph_data:/data
    environment:
      - SEMANTIC_GRAPH_DEBUG=false
      - SEMANTIC_GRAPH_API_HOST=0.0.0.0
      - SEMANTIC_GRAPH_DATA_DIR=/data
    restart: unless-stopped
    healthcheck: ...
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: "2"
```

---

## 9. Database Migrations

### 9.1 Overview

Alembic manages schema migrations with support for both databases:

- `projects.db` — managed by Alembic (default target)
- `graph.db` — managed at runtime by `DatabaseManager` (creates tables on first access), with Alembic stamping for version tracking

### 9.2 Common Commands

```bash
# Apply migrations to projects.db (default)
alembic upgrade head

# Generate a new migration for projects.db
alembic revision --autogenerate -m "description of change"

# Graph schema migrations
alembic -x db=graph revision --autogenerate -m "description"
alembic -x db=graph upgrade head

# Target a specific project's graph.db
alembic -x db=graph -x project_id=<uuid> upgrade head

# Roll back one revision
alembic downgrade -1
```

### 9.3 How It Works

On startup, `DatabaseManager` creates tables via `ProjectsBase.metadata.create_all()` and `GraphBase.metadata.create_all()`, then stamps the database with the current Alembic head revision via `_stamp_if_configured()`. This is best-effort — if Alembic isn't installed or configured, stamping is silently skipped.

The `migrations/env.py` script:
1. Reads the `-x db=` argument to select `projects` or `graph` target
2. Expands `~` in the database URL and ensures parent directories exist
3. Selects the appropriate metadata (`ProjectsBase` or `GraphBase`) for autogenerate
4. For `graph` target, optionally accepts `-x project_id=<uuid>` to target a specific project

---

## 10. Code Quality

### 10.1 Linting and Formatting

```bash
# Run ruff linter
ruff check src/ tests/ migrations/

# Run ruff formatter
ruff format src/ tests/ migrations/

# Type check with mypy (strict mode)
mypy src/

# Run pre-commit on all files
pre-commit run --all-files
```

### 10.2 Ruff Configuration

- Target Python version: 3.11
- Rules: `E`, `W`, `F`, `I`, `UP`, `B`
- Format: double quotes, spaces
- Per-file ignore: `B008` in CLI files (Typer `Option()`/`Argument()` defaults)

### 10.3 Mypy Configuration

- Strict mode enabled
- `graph_tool` and `uvicorn` have `ignore_missing_imports` (no stubs available)
- Only checks `src/` directory

---

## 11. CI/CD

The CI pipeline runs on every push/PR to `main` (`.github/workflows/ci.yml`):

| Job | Steps |
|-----|-------|
| **Lint** | `ruff check`, `ruff format --check` |
| **Type check** | `mypy src/` |
| **Test** | `pytest --cov=semantic_graph --cov-report=xml` on Python 3.11 and 3.12 |

Coverage reports are uploaded as artifacts.

---

## 12. Development Conventions

### 12.1 Git Workflow

- **Branch naming**: `<username>/<short-description>` (e.g., `btabone/add-node-query`)
- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/) format:
  - `feat:` — new feature
  - `fix:` — bug fix
  - `chore:` — maintenance, dependencies
  - `docs:` — documentation
  - `refactor:` — code restructuring without behavior change
  - `test:` — adding or updating tests
- **Commit messages**: end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` when AI-assisted

### 12.2 Coding Style

- **Docstrings**: NumPy/Google-style with parameter descriptions
- **Type annotations**: All public functions must be fully typed (enforced by mypy strict mode)
- **Imports**: Absolute imports within the `semantic_graph` package; `from __future__ import annotations` in all modules
- **String quotes**: Double quotes (enforced by ruff)
- **Line length**: No strict limit enforced, but aim for readability

### 12.3 Testing Conventions

- Tests use `pytest` with fixtures
- In-memory SQLite is preferred for unit tests
- Database tests register an FK enforcement listener on each engine
- `DatabaseManager` tests use a `tempfile.TemporaryDirectory` for isolation
- Async tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Fixture files go in `tests/fixtures/`

---

## 13. Project Status

### Implemented (✅)

- Two-database SQLite architecture with ORM models
- Repository pattern with generic `BaseRepository`
- Graph engine with pluggable backends (NetworkX + graph-tool)
- Read/write separation with `GraphSyncManager`
- Graph queries: `get_node`, `get_neighbors`, `get_stats`
- Full project CRUD API endpoints
- File scanner with `.gitignore` support, binary detection, and path security
- CLI with version and project subcommands
- Alembic migrations for both databases
- Docker multi-stage build with non-root user
- CI pipeline (lint, type check, test on 3.11 and 3.12)
- Health check endpoint
- Security: path traversal protection, symlink safety, system directory rejection

### Stubs / Future Work (🚧)

- `ProjectManager` — scanning and processing job orchestration
- `GraphManager` — graph operations
- API routes: graph queries, LLM configuration
- `LLMManager` — provider orchestration and model selection
- `ExtractorRegistry` — extractor discovery and dispatch
- Concrete extractors: code (AST-based), documents, text
- Actual LLM-powered entity/relationship extraction pipeline
- Background job processing (scan → extract → build graph)
- Integration tests

---

## 14. Key Files Reference

| File | Purpose |
|------|---------|
| `src/semantic_graph/storage/database.py` | Database connection management, two-DB architecture |
| `src/semantic_graph/storage/models.py` | All ORM models |
| `src/semantic_graph/graph_engine/backends.py` | Graph backend ABC + implementations |
| `src/semantic_graph/graph_engine/sync.py` | Write path with deferred SQLite persistence |
| `src/semantic_graph/graph_engine/graph_builder.py` | Load graph from SQLite into memory |
| `src/semantic_graph/graph_engine/queries.py` | Read queries (node, neighbors, stats) |
| `src/semantic_graph/core/config.py` | Application settings |
| `src/semantic_graph/core/project_manager.py` | Project business logic |
| `src/semantic_graph/api/main.py` | FastAPI application entry point |
| `src/semantic_graph/api/routes/projects.py` | Project REST endpoints |
| `src/semantic_graph/cli/main.py` | CLI application entry point |
| `src/semantic_graph/extractors/scanner.py` | File system scanner |
| `src/semantic_graph/utils/security.py` | Path security and validation |
| `src/semantic_graph/utils/errors.py` | Exception hierarchy |
| `pyproject.toml` | Project metadata, dependencies, tool config |
| `migrations/env.py` | Alembic environment (two-DB aware) |
| `Dockerfile` | Multi-stage Docker build |
| `docker-compose.yml` | Docker Compose service definition |
| `.github/workflows/ci.yml` | CI pipeline |

---

## 15. Glossary

| Term | Definition |
|------|-----------|
| **Project** | A user-defined scope: a root directory + scan configuration |
| **Node** | A semantic entity in the graph (function, class, concept, etc.) |
| **Edge** | A directed relationship between nodes (calls, imports, references, etc.) |
| **Abstraction Level** | Granularity of a node: `"fine"` (e.g., function), `"mid"` (e.g., module), `"high"` (e.g., concept) |
| **GraphBuildResult** | In-memory representation of a loaded graph + UUID↔index mappings |
| **GraphSyncManager** | Write path that stages mutations and syncs to SQLite atomically |
| **Extractor** | A component that parses a file and produces nodes/edges |
| **FileManifestEntry** | Tracks processing state for a single file (hash, status, extractor) |
| **ProcessingJob** | Tracks an async processing operation (scan, extract, build) |
