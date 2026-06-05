# Semantic Graph Manager

## Project Overview

Semantic Graph Manager is a tool to create, manage, and query semantic graphs from user-defined data folders. The system extracts entities and relationships from diverse data sources (code, documents, media references) using LLM-powered semantic analysis, storing them in a graph structure accessible via a REST API and CLI.

---

## Prerequisites

- **Python ≥ 3.11**
- **git**
- **graph-tool** — *not available on PyPI*; install via your system package manager, conda, or the project Docker image. See the [graph-tool installation guide](https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions). The system runs in a NetworkX-based fallback mode for development and small graphs without graph-tool, but the 100K-node performance target requires graph-tool.

---

## Quick Start (Developer Setup)

```bash
git clone https://github.com/hybridmachine/semantic-graph
cd semantic-graph
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

---

## Running the Server

```bash
# Via Uvicorn directly
uvicorn semantic_graph.api.main:app --reload

# Via the installed entry point
semantic-graph-server
```

The API will be available at `http://localhost:8000`. Health check: `GET /api/v1/health`.

---

## Running the CLI

```bash
semantic-graph --help
semantic-graph version
```

---

## Running Tests

```bash
pytest
# With coverage
pytest --cov=semantic_graph --cov-report=term-missing
```

---

## Docker

```bash
docker compose up
```

> **Note**: The current Docker stub does **not** include graph-tool. Production graph-tool installation still needs to be added to the Dockerfile.

---

## Configuration

Configuration files live in `configs/`. The application reads settings from environment variables prefixed with `SEMANTIC_GRAPH_` and from a `.env` file in the project root.

| Variable | Default | Description |
|---|---|---|
| `SEMANTIC_GRAPH_DEBUG` | `false` | Enable debug mode |
| `SEMANTIC_GRAPH_API_HOST` | `127.0.0.1` | Server bind host. Defaults to loopback for local security; set to `0.0.0.0` when running in Docker or on a LAN |
| `SEMANTIC_GRAPH_API_PORT` | `8000` | Server bind port |
| `SEMANTIC_GRAPH_DATA_DIR` | `~/.semantic-graph` | Application data directory |

---

## Contributing

- **Branch naming**: `<username>/<short-description>` (e.g. `alice/add-openai-provider`)
- **Commit style**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, etc.)
- **PR checklist**: All CI jobs green, tests added/updated, docstrings present for public APIs
