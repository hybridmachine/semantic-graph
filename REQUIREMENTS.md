# Semantic Graph Manager - Requirements Specification

## 1. Project Overview

A tool to create, manage, and query semantic graphs from user-defined data folders. The system extracts entities and relationships from diverse data sources (code, documents, media references) using LLM-powered semantic analysis, storing them in a graph structure accessible via REST API.

### Core Value Proposition
- **Human-centric navigation**: Start high-level, drill down into details
- **Universal applicability**: Works with code, documents, mixed projects
- **Extensible architecture**: Pluggable extractors, LLM providers, and frontends
- **Local-first, cloud-ready**: Starts as local tool, designed for future cloud deployment

---

## 2. Functional Requirements

Requirement IDs are stable references. New requirements use the next available ID even when grouped under an earlier functional area.

### 2.1 Project Management
- **FR-01**: Users can register a "project" pointing to a local folder path
- **FR-02**: Users can configure which file types/patterns to include/exclude per project
- **FR-03**: Users can trigger graph generation/update for a specific project
- **FR-04**: Users can view project status (last updated, node/edge counts, errors)
- **FR-05**: Users can delete a project registration and generated graph data without deleting the source folder; optional export should be offered before deletion

### 2.2 Graph Generation & Updates
- **FR-06**: System scans registered project folders for files matching inclusion rules
- **FR-07**: System extracts content from supported file types (text, code, markdown, etc.)
- **FR-08**: LLM analyzes content to identify:
  - Entities/concepts (nodes)
  - Relationships between entities (edges)
  - Abstraction level markers (high/mid/fine-grain)
- **FR-09**: System supports incremental updates (only re-process changed files)
- **FR-10**: System tracks processing errors per file without halting entire job
- **FR-11**: Users can force full rebuild of project graph (bypasses LLM cache — all files re-analyzed fresh)
- **FR-41**: Incremental updates use content hashes as the source of truth for change detection; file size and modification time may be used only as optimizations
- **FR-42**: Incremental updates handle deleted files, renamed files, and include/exclude rule changes by removing stale nodes, edges, cache references, and file manifest entries
- **FR-43**: The scanner respects `.gitignore` by default (configurable) and excludes common generated/dependency folders such as `.git`, `node_modules`, `.venv`, `__pycache__`, `dist`, and `build`
- **FR-44**: Unsupported, binary, unreadable, and oversized files are skipped with a recorded per-file reason; maximum file size is configurable globally and per project
- **FR-47**: System normalizes and deduplicates extracted entities using deterministic canonicalization rules before writing graph data; aliases and conflicting candidates are preserved in metadata for review

### 2.3 LLM Integration
- **FR-12**: Pluggable LLM provider architecture supporting:
  - OpenAI API
  - Anthropic Claude API
  - Local models (Ollama, LM Studio, etc.)
  - Future providers via plugin interface
- **FR-13**: Users configure default LLM provider globally and per-project
- **FR-14**: System handles rate limiting, retries, and cost tracking per provider
- **FR-15**: Users can set token limits and model parameters per project
- **FR-16**: Support for streaming responses for long-running analyses
- **FR-38**: Cache LLM responses using a composite key derived from file content hash, prompt template hash/version, extraction schema version, extractor ID/version, provider, model, and model parameter hash. On graph generation, check cache before calling LLM; reuse cached response on hit, call LLM and store result on miss. Cache is stored in the per-project SQLite database.
- **FR-39**: Users can clear the LLM cache for a project without rebuilding the graph. The graph structure remains intact; only cached LLM responses are deleted. Next scan will re-call the LLM for all files fresh.
- **FR-45**: LLM responses must conform to a versioned JSON extraction schema; malformed or incomplete responses are rejected, logged, and retried according to the provider retry policy before being marked as file-level errors
- **FR-46**: Cloud LLM providers require explicit configuration and visible disclosure that project file contents may be sent to an external service; local providers can be selected as the privacy-preserving default

### 2.4 Graph Storage & Querying
- **FR-17**: Store graph persistently in SQLite and load it into graph-tool for efficient in-memory operations
- **FR-18**: Support node properties:
  - ID, name, type, abstraction_level, source_file, content_snippet, metadata (JSON)
- **FR-19**: Support edge properties:
  - ID, source_node, target_node, relationship_type, confidence_score, metadata (JSON)
- **FR-20**: Query endpoints for:
  - Get node by ID
  - Get neighbors of a node (configurable depth)
  - Search nodes by text/properties
  - Find paths between nodes
  - Get subgraph by abstraction level
  - Get statistics (node/edge counts, distributions)
- **FR-21**: Support filtering queries by:
  - Node/edge type
  - Abstraction level
  - Source file
  - Confidence score threshold
  - Custom metadata fields

### 2.5 REST API
- **FR-22**: RESTful endpoints following standard conventions (GET/POST/PUT/DELETE)
- **FR-23**: JSON request/response format
- **FR-24**: Pagination for list endpoints
- **FR-25**: Async operation support for long-running tasks (graph generation)
- **FR-26**: Health check endpoint
- **FR-27**: API versioning strategy (URL-based: /api/v1/)
- **FR-28**: CORS support for future web frontend
- **FR-29**: Basic authentication/token-based auth (foundation for cloud)
- **FR-50**: Users can cancel long-running jobs; cancellation is cooperative, stops at safe checkpoints, and leaves the graph in the last transactionally consistent state

### 2.6 CLI Client
- **FR-30**: CLI commands mirroring REST API functionality:
  - `project create/list/delete/configure`
  - `graph generate/status/query`
  - `llm configure/test`
  - `config show/set`
- **FR-31**: Interactive mode for exploring graph (text-based navigation)
- **FR-32**: Output formats: JSON, table, tree visualization (ASCII)
- **FR-33**: Configuration management (local config file)
- **FR-40**: Clear LLM response cache for a project: `graph cache-clear [--project NAME]`
- **FR-51**: CLI supports operational commands for `job cancel`, `graph export`, and `graph import`

### 2.7 File Extraction
- **FR-34**: Pluggable extractor architecture for file types
- **FR-35**: Built-in extractors for:
  - Plain text (.txt, .md, .rst)
  - Code files (.py, .js, .java, .cpp, etc.)
  - Documents (.pdf, .docx - via external tools)
  - Configuration files (.yaml, .json, .toml)
- **FR-36**: Extractors return structured content + metadata for LLM processing
- **FR-37**: Users can add custom extractors via plugin system

### 2.8 Backup, Export & Restore
- **FR-48**: Users can export a project graph, project metadata, file manifest, and optional LLM cache to portable formats including JSON and GraphML
- **FR-49**: Users can import/restore a previously exported project into a new project ID without overwriting existing projects unless explicitly requested

---

## 3. Non-Functional Requirements

NFR IDs are stable references. New requirements use the next available ID even when grouped under an earlier non-functional area.

### 3.1 Performance
- **NFR-01**: Standard graph queries return P95 results in under 500ms for graphs up to 100K nodes on supported consumer hardware
- **NFR-02**: Incremental updates process only changed or otherwise affected files
- **NFR-03**: Support concurrent requests (async server architecture)
- **NFR-04**: Efficient storage: under 1KB average per node in database

### 3.2 Scalability
- **NFR-05**: Architecture supports migration to PostgreSQL/Neo4j for larger graphs
- **NFR-06**: API request handling remains stateless, but in-memory graph caches are process-local and must be rebuildable from SQLite; horizontal scaling requires explicit cache invalidation or an external graph service
- **NFR-07**: Support multiple independent projects without performance degradation

### 3.3 Reliability
- **NFR-08**: Graceful handling of LLM API failures with bounded retries, exponential backoff, and provider-specific rate-limit handling
- **NFR-09**: Transaction safety for graph updates; failed or cancelled jobs must not expose partial graph writes
- **NFR-10**: Comprehensive error logging with context
- **NFR-11**: Data backup/export/import functionality with documented restore procedure
- **NFR-27**: Crash recovery restores the last-good graph state from SQLite and marks interrupted jobs as failed or resumable with actionable error context

### 3.4 Security
- **NFR-12**: Input validation on all endpoints
- **NFR-13**: Path traversal protection for file access
- **NFR-14**: Secure storage of API keys using OS keychain where available, or encrypted-at-rest configuration with restrictive file permissions
- **NFR-15**: Rate limiting per client (future cloud readiness)
- **NFR-24**: Local server binds to `127.0.0.1` by default; remote bind addresses and CORS origins require explicit configuration
- **NFR-25**: Logs and error responses redact API keys, tokens, raw file content, and provider request payloads by default
- **NFR-26**: Symlinks are not followed outside the project root by default; path canonicalization is required before file access

### 3.5 Usability
- **NFR-16**: Clear error messages with actionable guidance
- **NFR-17**: Progress indicators for long-running operations
- **NFR-18**: Comprehensive CLI help and documentation
- **NFR-19**: OpenAPI/Swagger documentation for REST API

### 3.6 Maintainability
- **NFR-20**: Modular architecture with clear separation of concerns
- **NFR-21**: Plugin interfaces clearly documented
- **NFR-22**: Test coverage >80% for core logic
- **NFR-23**: Docker support for easy deployment

---

## 4. Technical Architecture

### 4.1 High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Client                             │
│            (FastAPI/HTTP client + Rich for TUI)             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    REST API Server                          │
│       (FastAPI, async, stateless request handling)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Projects │  │  Graph   │  │   LLM    │  │   Auth   │   │
│  │  Router  │  │  Router  │  │  Router  │  │  Router  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Service    │    │   Service    │    │   Service    │
│    Layer     │    │    Layer     │    │    Layer     │
│ (Business    │    │ (Business    │    │ (Business    │
│  Logic)      │    │  Logic)      │    │  Logic)      │
└──────────────┘    └──────────────┘    └──────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Per-Project  │    │  graph-tool  │    │ LLM Provider │
│   SQLite     │◄──►│   (In-mem    │    │   Manager    │
│     DBs      │    │   Graph Ops) │    │  (Pluggable) │
└──────────────┘    └──────────────┘    └──────────────┘
       │                    │
       │  Writes on sync    │  Reads served
       │  boundaries only   │  directly from
       ▼                    ▼
  ┌──────────────────────────────────┐
  │  ~/.semantic-graph/              │
  │  ├── projects.db  (shared meta)  │
  │  └── projects/                   │
  │      └── <id>/graph.db           │
  └──────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   File System    │
                    │  (Project Data)  │
                    └──────────────────┘
```

### 4.2 Directory Structure

```
semantic-graph/
├── src/
│   └── semantic_graph/
│       ├── api/                  # REST API layer
│       │   ├── __init__.py
│       │   ├── main.py           # FastAPI app entry
│       │   ├── routes/           # API route handlers
│       │   │   ├── projects.py
│       │   │   ├── graph.py
│       │   │   ├── llm.py
│       │   │   └── health.py
│       │   ├── middleware/       # Auth, CORS, logging
│       │   └── schemas/          # Pydantic models
│       ├── cli/                  # Command-line interface
│       │   ├── __init__.py
│       │   ├── main.py           # CLI entry point
│       │   ├── commands/         # CLI command groups
│       │   └── formatters/       # Output formatters
│       ├── core/                 # Business logic
│       │   ├── __init__.py
│       │   ├── graph_manager.py  # Graph operations
│       │   ├── project_manager.py
│       │   └── config.py
│       ├── storage/              # Data persistence
│       │   ├── __init__.py
│       │   ├── database.py       # SQLite connection
│       │   ├── models.py         # SQLAlchemy models
│       │   └── repositories/     # Data access layer
│       ├── graph_engine/         # Graph-tool integration
│       │   ├── __init__.py
│       │   ├── graph_builder.py
│       │   └── queries.py
│       ├── llm/                  # LLM integration
│       │   ├── __init__.py
│       │   ├── provider_base.py  # Abstract base class
│       │   ├── providers/        # Concrete implementations
│       │   │   ├── openai.py
│       │   │   ├── anthropic.py
│       │   │   └── ollama.py
│       │   ├── manager.py        # Provider selection/routing
│       │   └── prompts/          # Prompt templates
│       ├── extractors/           # File content extraction
│       │   ├── __init__.py
│       │   ├── base.py           # Extractor interface
│       │   ├── registry.py       # Extractor discovery
│       │   └── builtins/         # Built-in extractors
│       │       ├── text.py
│       │       ├── code.py
│       │       └── documents.py
│       └── utils/                # Shared utilities
│           ├── logging.py
│           ├── errors.py
│           └── helpers.py
├── tests/                    # Test suite
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── migrations/               # Database migrations
├── configs/                  # Example configurations
├── docs/                     # Documentation
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

### 4.3 Data Models

#### Project
```python
{
    "id": "uuid",
    "name": "string",
    "root_path": "string (absolute path)",
    "include_patterns": ["list of glob patterns"],
    "exclude_patterns": ["list of glob patterns"],
    "respect_gitignore": "boolean",
    "default_excludes": ["list of glob patterns"],
    "max_file_size_bytes": "integer",
    "follow_symlinks": "boolean",
    "llm_provider": "string (provider name)",
    "llm_model": "string",
    "llm_parameters": "json (model-specific settings)",
    "created_at": "datetime",
    "updated_at": "datetime",
    "status": "idle|processing|error"
}
```

#### Node
```python
{
    "id": "uuid",
    "project_id": "uuid (foreign key)",
    "name": "string",
    "type": "string (concept, file, function, class, etc.)",
    "abstraction_level": "high|mid|fine",
    "source_file": "string (relative path)",
    "content_snippet": "text",
    "metadata": "json (stored as TEXT/JSON in SQLite)",
    "created_at": "datetime",
    "updated_at": "datetime"
}
```

#### Edge
```python
{
    "id": "uuid",
    "project_id": "uuid (foreign key)",
    "source_node_id": "uuid (foreign key)",
    "target_node_id": "uuid (foreign key)",
    "relationship_type": "string",
    "confidence_score": "float (0-1)",
    "metadata": "json (stored as TEXT/JSON in SQLite)",
    "created_at": "datetime"
}
```

#### Processing Job
```python
{
    "id": "uuid",
    "project_id": "uuid",
    "type": "full|incremental",
    "status": "pending|running|completed|failed|cancelled",
    "progress": "integer (0-100)",
    "files_processed": "integer",
    "files_total": "integer",
    "errors": "json (stored as TEXT/JSON in SQLite; list of error objects)",
    "started_at": "datetime",
    "cancel_requested_at": "datetime|null",
    "completed_at": "datetime"
}
```

#### File Manifest Entry
```python
{
    "id": "uuid",
    "project_id": "uuid",
    "relative_path": "string",
    "content_hash": "string (SHA256 of file content)",
    "size_bytes": "integer",
    "modified_at": "datetime",
    "extractor_id": "string",
    "extractor_version": "string",
    "status": "pending|processed|skipped|error|deleted",
    "skip_reason": "string|null",
    "last_processed_at": "datetime|null"
}
```

#### LLM Extraction Result (versioned schema)
```python
{
    "schema_version": "string",
    "nodes": [
        {
            "name": "string",
            "type": "string",
            "abstraction_level": "high|mid|fine",
            "confidence_score": "float (0-1)",
            "aliases": ["list of strings"],
            "metadata": "json"
        }
    ],
    "edges": [
        {
            "source": "node reference",
            "target": "node reference",
            "relationship_type": "string",
            "confidence_score": "float (0-1)",
            "metadata": "json"
        }
    ],
    "warnings": ["list of strings"]
}
```

#### LLM Cache Entry (per-project DB)
```python
{
    "id": "uuid",
    "cache_key": "string (SHA256 of normalized cache key components)",
    "file_hash": "string (SHA256 of file content)",
    "prompt_hash": "string (SHA256 of prompt template)",
    "prompt_version": "string",
    "schema_version": "string",
    "extractor_id": "string",
    "extractor_version": "string",
    "provider": "string",
    "model": "string",
    "model_parameters_hash": "string",
    "response_json": "json (LLM response, stored as TEXT/JSON in SQLite)",
    "token_usage": "json ({prompt_tokens, completion_tokens, total_tokens})",
    "created_at": "datetime"
}
```
**Cache key**: normalized hash of file content, prompt, schema, extractor, provider, model, and model parameters. Clearing the cache (via API or CLI) deletes all entries for the project without affecting the graph.

### 4.4 API Endpoints (v1)

#### Projects
- `POST /api/v1/projects` - Create project
- `GET /api/v1/projects` - List projects
- `GET /api/v1/projects/{id}` - Get project details
- `PUT /api/v1/projects/{id}` - Update project config
- `DELETE /api/v1/projects/{id}` - Delete project
- `POST /api/v1/projects/{id}/scan` - Trigger graph generation (`mode=incremental|full`)
- `GET /api/v1/projects/{id}/files` - List file manifest entries, including skip/error status
- `GET /api/v1/projects/{id}/export` - Export project metadata and graph data
- `POST /api/v1/projects/import` - Import/restore exported project data

#### Graph
- `GET /api/v1/graph/{project_id}/nodes/{node_id}` - Get node
- `GET /api/v1/graph/{project_id}/nodes` - Search/list nodes
- `GET /api/v1/graph/{project_id}/nodes/{node_id}/neighbors` - Get neighbors
- `GET /api/v1/graph/{project_id}/edges` - List/search edges
- `GET /api/v1/graph/{project_id}/path` - Find path between nodes
- `GET /api/v1/graph/{project_id}/subgraph` - Get subgraph by criteria
- `GET /api/v1/graph/{project_id}/stats` - Get graph statistics
- `DELETE /api/v1/graph/{project_id}/cache` - Clear LLM response cache
- `POST /api/v1/graph/{project_id}/sync` - Force sync in-memory graph to SQLite

#### Jobs
- `GET /api/v1/jobs/{job_id}` - Get job status
- `GET /api/v1/jobs` - List jobs (with filters)
- `DELETE /api/v1/jobs/{job_id}` - Cancel job

Job cancellation is cooperative: running jobs stop at the next safe checkpoint, mark unprocessed files as pending/skipped, and leave the visible graph at the last-good committed state.

#### LLM Configuration
- `GET /api/v1/llm/providers` - List available providers
- `POST /api/v1/llm/providers/{name}/configure` - Configure provider
- `POST /api/v1/llm/test` - Test LLM connection

#### System
- `GET /api/v1/health` - Health check
- `GET /api/v1/version` - API version info

---

## 5. Implementation Phases

### Phase 1: Foundation (MVP)
- [ ] Project setup and structure
- [ ] SQLite database with basic models
- [ ] graph-tool integration (load/save from SQLite)
- [ ] Basic REST API (FastAPI) with project CRUD
- [ ] Simple file scanner (no LLM yet)
- [ ] CLI for project management
- [ ] Docker configuration

### Phase 2: LLM Integration
- [ ] LLM provider base class and interface
- [ ] OpenAI provider implementation
- [ ] Anthropic provider implementation
- [ ] Ollama (local) provider implementation
- [ ] Versioned extraction schema and response validation
- [ ] Prompt engineering for entity/relation extraction
- [ ] LLM response caching (composite content/prompt/schema/model/extractor key)
- [ ] Graph generation pipeline with LLM
- [ ] Job tracking for async operations

### Phase 3: Graph Operations
- [ ] Advanced graph queries (neighbors, paths, subgraphs)
- [ ] Search functionality (text search, filter by properties)
- [ ] Abstraction level navigation
- [ ] Incremental update logic
- [ ] File manifest tracking for changed, deleted, skipped, and errored files
- [ ] CLI graph exploration commands

### Phase 4: Polish & Extensibility
- [ ] Additional extractors (PDF, DOCX)
- [ ] Plugin system documentation
- [ ] Comprehensive error handling
- [ ] Logging and monitoring
- [ ] Performance optimization
- [ ] OpenAPI documentation
- [ ] Test suite completion

### Phase 5: Production Readiness
- [ ] Authentication system
- [ ] Rate limiting
- [ ] Backup/export/import functionality
- [ ] Migration scripts
- [ ] Deployment documentation
- [ ] Cloud deployment preparation

---

## 6. Key Design Decisions & Rationale

### 6.1 Why FastAPI?
- Async support for concurrent LLM calls and DB operations
- Automatic OpenAPI documentation
- Pydantic integration for validation
- Easy testing with TestClient
- Production-ready with uvicorn/gunicorn

### 6.2 Why SQLite + graph-tool?
- **SQLite**: Zero-config, portable, sufficient for medium graphs (under 1M nodes), easy migration to PostgreSQL
- **graph-tool**: Extremely fast graph algorithms (C++ backend), better than NetworkX for large graphs
- **Hybrid approach**: SQLite for persistence, graph-tool loaded in-memory for all read operations
  - **Reads**: All graph queries (neighbors, paths, search, stats) hit the in-memory graph-tool graph directly — no SQLite round-trip
  - **Writes**: SQLite is updated only at sync boundaries (job completion, explicit sync, graceful shutdown). On startup, the graph is loaded from SQLite into graph-tool memory. If a crash occurs mid-processing, SQLite retains the last-good state.
  - **One DB per project**: A shared `projects.db` stores project-level metadata; each project gets its own SQLite file for graph data (nodes, edges, jobs, LLM cache). This enables independent backup/delete per project and prevents cross-project query contamination.
- **Runtime process model**: The MVP assumes one authoritative in-memory graph cache per running API process. The cache is always rebuildable from SQLite, and multi-worker/cloud deployments must add cache invalidation or an external graph service before horizontal scaling is enabled.
- **Concurrency model**: Only one write job may update a project graph at a time. Reads continue against the last-good committed graph while writes are staged and committed at safe sync boundaries.

### 6.3 Why Pluggable LLM Architecture?
- Avoid vendor lock-in
- Support cost optimization (choose model per task)
- Enable local model usage for privacy/sensitivity
- Future-proof for new providers

### 6.4 Why REST First?
- Universal accessibility (CLI, web, mobile, third-party)
- Clear contract for future frontends
- Easy testing and documentation
- Stateless request contracts simplify cloud scaling; process-local graph caches are treated as rebuildable implementation details

### 6.5 Abstraction Level Strategy
- **High**: Projects, folders, major sections
- **Mid**: Files, chapters, modules, classes
- **Fine**: Functions, concepts, variables, specific topics
- LLM prompted to categorize during extraction
- Enables progressive disclosure in UI/future visualizers

### 6.6 Package Layout
- Use a `src/semantic_graph/` package layout to avoid top-level import collisions and keep API, CLI, core, storage, graph engine, LLM, and extractor modules under one distributable Python package.

### 6.7 graph-tool Fallback Scope
- graph-tool is the production graph engine for the stated performance targets.
- A NetworkX fallback may be provided for development, tests, or small local graphs, but it is explicitly outside the 100K-node performance target unless separately benchmarked.

---

## 7. Open Questions & Considerations

### 7.1 Remaining Decisions
1. **Vector embeddings**: Add later for semantic search, or build in from start?
2. **Human review workflow**: Should low-confidence entities/edges require explicit review before becoming visible in default graph queries?
3. **Plugin API stability**: What versioning guarantees should extractor and LLM provider plugins receive before 1.0?
4. **Graph versioning**: Should each successful generation job create a queryable graph snapshot, or should versioning remain an export/diff feature for later?

### 7.2 Potential Future Enhancements
- **File watching**: Auto-trigger incremental scans on file changes (create, modify, delete) within project folders. The scanner component will expose a clean interface (`scan(project, paths)`) so a future `watch(project)` can reuse the same scan logic, feeding it changed paths from filesystem events (e.g., via `watchfiles` or `inotify`).
- Real-time collaboration (multiple users on same graph)
- Graph versioning and diffing
- Additional export formats (GEXF, DOT)
- Web-based visualizer (D3.js, Cytoscape.js)
- Knowledge graph reasoning/inference
- Integration with existing tools (Obsidian, Roam, IDEs)
- Automated summarization at each abstraction level

---

## 8. Success Metrics

### Technical
- P95 API response time under 500ms for standard graph queries against 100K-node graphs on supported consumer hardware
- Incremental scans reprocess only files whose content hash, inclusion status, or extractor/schema inputs changed
- Failed, cancelled, or interrupted graph generation jobs leave the visible graph at the last-good committed state
- LLM extraction validation catches malformed responses before graph writes; file-level failures remain below 5% on representative supported file sets after retries

### User Experience
- Project setup in under 5 minutes
- First graph generated in under 10 minutes for typical project
- CLI intuitive enough for non-developers
- Clear progress feedback during long operations

### Business (Future)
- Easy migration path to cloud hosting
- Multi-user support without architectural changes
- Usage metering capability for billing

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM costs spiral out of control | High | Token limits, response caching (FR-38), local model fallback, cost tracking |
| Cloud LLM privacy exposure | High | Explicit provider configuration, disclosure before sending file content externally, local provider option |
| graph-tool installation complexity | Medium | Provide Docker, detailed install docs, optional NetworkX fallback for dev/small graphs only |
| SQLite performance at scale | Medium | Monitor benchmarks, design for PostgreSQL migration |
| LLM extraction quality varies | High | Configurable prompts, human review workflow, confidence scores |
| File type support insufficient | Medium | Plugin architecture, community contributions |
| Stale in-memory graph cache | Medium | Single-writer project locking, cache rebuild from SQLite, explicit invalidation before multi-worker deployment |

---

## 10. Next Steps

1. **Review & Refine**: Stakeholder review of requirements
2. **Technical Spikes**: 
   - graph-tool + SQLite integration prototype
   - LLM provider interface design
   - Versioned LLM extraction schema and validation strategy
   - File manifest and incremental update prototype
   - FastAPI async pattern validation
3. **Prioritize Phase 1 Tasks**: Break down into actionable tickets
4. **Set Up Development Environment**: Repo, CI/CD, linting, testing framework
5. **Begin Phase 1 Implementation**

---

*Document Version: 1.2*
*Last Updated: 2026-06-03*
*Status: Draft for Review*
