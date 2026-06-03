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

### 2.1 Project Management
- **FR-01**: Users can register a "project" pointing to a local folder path
- **FR-02**: Users can configure which file types/patterns to include/exclude per project
- **FR-03**: Users can trigger graph generation/update for a specific project
- **FR-04**: Users can view project status (last updated, node/edge counts, errors)
- **FR-05**: Users can delete a project (optionally retaining raw data)

### 2.2 Graph Generation & Updates
- **FR-06**: System scans registered project folders for files matching inclusion rules
- **FR-07**: System extracts content from supported file types (text, code, markdown, etc.)
- **FR-08**: LLM analyzes content to identify:
  - Entities/concepts (nodes)
  - Relationships between entities (edges)
  - Abstraction level markers (high/mid/fine-grain)
- **FR-09**: System supports incremental updates (only re-process changed files)
- **FR-10**: System tracks processing errors per file without halting entire job
- **FR-11**: Users can force full rebuild of project graph

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

### 2.4 Graph Storage & Querying
- **FR-17**: Store graph in SQLite with graph-tool for efficient operations
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

### 2.6 CLI Client
- **FR-30**: CLI commands mirroring REST API functionality:
  - `project create/list/delete/configure`
  - `graph generate/status/query`
  - `llm configure/test`
  - `config show/set`
- **FR-31**: Interactive mode for exploring graph (text-based navigation)
- **FR-32**: Output formats: JSON, table, tree visualization (ASCII)
- **FR-33**: Configuration management (local config file)

### 2.7 File Extraction
- **FR-34**: Pluggable extractor architecture for file types
- **FR-35**: Built-in extractors for:
  - Plain text (.txt, .md, .rst)
  - Code files (.py, .js, .java, .cpp, etc.)
  - Documents (.pdf, .docx - via external tools)
  - Configuration files (.yaml, .json, .toml)
- **FR-36**: Extractors return structured content + metadata for LLM processing
- **FR-37**: Users can add custom extractors via plugin system

---

## 3. Non-Functional Requirements

### 3.1 Performance
- **NFR-01**: Graph queries return results in under 500ms for graphs up to 100K nodes
- **NFR-02**: Incremental updates process only changed files
- **NFR-03**: Support concurrent requests (async server architecture)
- **NFR-04**: Efficient storage: under 1KB average per node in database

### 3.2 Scalability
- **NFR-05**: Architecture supports migration to PostgreSQL/Neo4j for larger graphs
- **NFR-06**: Horizontal scaling design for future cloud deployment (stateless API layer)
- **NFR-07**: Support multiple independent projects without performance degradation

### 3.3 Reliability
- **NFR-08**: Graceful handling of LLM API failures (retry with backoff)
- **NFR-09**: Transaction safety for graph updates
- **NFR-10**: Comprehensive error logging with context
- **NFR-11**: Data backup/export functionality

### 3.4 Security
- **NFR-12**: Input validation on all endpoints
- **NFR-13**: Path traversal protection for file access
- **NFR-14**: Secure storage of API keys (encrypted at rest)
- **NFR-15**: Rate limiting per client (future cloud readiness)

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
│              (FastAPI, async, stateless)                    │
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
│   SQLite     │    │  graph-tool  │    │ LLM Provider │
│  Database    │◄──►│   (In-mem    │    │   Manager    │
│  (Persist)   │    │   Graph Ops) │    │  (Pluggable) │
└──────────────┘    └──────────────┘    └──────────────┘
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
│   ├── api/                  # REST API layer
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app entry
│   │   ├── routes/           # API route handlers
│   │   │   ├── projects.py
│   │   │   ├── graph.py
│   │   │   ├── llm.py
│   │   │   └── health.py
│   │   ├── middleware/       # Auth, CORS, logging
│   │   └── schemas/          # Pydantic models
│   ├── core/                 # Business logic
│   │   ├── __init__.py
│   │   ├── graph_manager.py  # Graph operations
│   │   ├── project_manager.py
│   │   └── config.py
│   ├── storage/              # Data persistence
│   │   ├── __init__.py
│   │   ├── database.py       # SQLite connection
│   │   ├── models.py         # SQLAlchemy models
│   │   └── repositories/     # Data access layer
│   ├── graph_engine/         # Graph-tool integration
│   │   ├── __init__.py
│   │   ├── graph_builder.py
│   │   └── queries.py
│   ├── llm/                  # LLM integration
│   │   ├── __init__.py
│   │   ├── provider_base.py  # Abstract base class
│   │   ├── providers/        # Concrete implementations
│   │   │   ├── openai.py
│   │   │   ├── anthropic.py
│   │   │   └── ollama.py
│   │   ├── manager.py        # Provider selection/routing
│   │   └── prompts/          # Prompt templates
│   ├── extractors/           # File content extraction
│   │   ├── __init__.py
│   │   ├── base.py           # Extractor interface
│   │   ├── registry.py       # Extractor discovery
│   │   └── builtins/         # Built-in extractors
│   │       ├── text.py
│   │       ├── code.py
│   │       └── documents.py
│   └── utils/                # Shared utilities
│       ├── logging.py
│       ├── errors.py
│       └── helpers.py
├── cli/                      # Command-line interface
│   ├── __init__.py
│   ├── main.py               # CLI entry point
│   ├── commands/             # CLI command groups
│   └── formatters/           # Output formatters
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
    "llm_provider": "string (provider name)",
    "llm_model": "string",
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
    "metadata": "jsonb",
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
    "metadata": "jsonb",
    "created_at": "datetime"
}
```

#### Processing Job
```python
{
    "id": "uuid",
    "project_id": "uuid",
    "type": "full|incremental",
    "status": "pending|running|completed|failed",
    "progress": "integer (0-100)",
    "files_processed": "integer",
    "files_total": "integer",
    "errors": "jsonb (list of error objects)",
    "started_at": "datetime",
    "completed_at": "datetime"
}
```

### 4.4 API Endpoints (v1)

#### Projects
- `POST /api/v1/projects` - Create project
- `GET /api/v1/projects` - List projects
- `GET /api/v1/projects/{id}` - Get project details
- `PUT /api/v1/projects/{id}` - Update project config
- `DELETE /api/v1/projects/{id}` - Delete project
- `POST /api/v1/projects/{id}/scan` - Trigger graph generation

#### Graph
- `GET /api/v1/graph/{project_id}/nodes/{node_id}` - Get node
- `GET /api/v1/graph/{project_id}/nodes` - Search/list nodes
- `GET /api/v1/graph/{project_id}/nodes/{node_id}/neighbors` - Get neighbors
- `GET /api/v1/graph/{project_id}/edges` - List/search edges
- `GET /api/v1/graph/{project_id}/path` - Find path between nodes
- `GET /api/v1/graph/{project_id}/subgraph` - Get subgraph by criteria
- `GET /api/v1/graph/{project_id}/stats` - Get graph statistics

#### Jobs
- `GET /api/v1/jobs/{job_id}` - Get job status
- `GET /api/v1/jobs` - List jobs (with filters)
- `DELETE /api/v1/jobs/{job_id}` - Cancel job

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
- [ ] Prompt engineering for entity/relation extraction
- [ ] Graph generation pipeline with LLM
- [ ] Job tracking for async operations

### Phase 3: Graph Operations
- [ ] Advanced graph queries (neighbors, paths, subgraphs)
- [ ] Search functionality (text search, filter by properties)
- [ ] Abstraction level navigation
- [ ] Incremental update logic
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
- [ ] Backup/export functionality
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
- **SQLite**: Zero-config, portable, sufficient for medium graphs (<1M nodes), easy migration to PostgreSQL
- **graph-tool**: Extremely fast graph algorithms (C++ backend), better than NetworkX for large graphs
- **Hybrid approach**: SQLite for persistence/querying, graph-tool loaded in-memory for complex operations

### 6.3 Why Pluggable LLM Architecture?
- Avoid vendor lock-in
- Support cost optimization (choose model per task)
- Enable local model usage for privacy/sensitivity
- Future-proof for new providers

### 6.4 Why REST First?
- Universal accessibility (CLI, web, mobile, third-party)
- Clear contract for future frontends
- Easy testing and documentation
- Stateless design enables cloud scaling

### 6.5 Abstraction Level Strategy
- **High**: Projects, folders, major sections
- **Mid**: Files, chapters, modules, classes
- **Fine**: Functions, concepts, variables, specific topics
- LLM prompted to categorize during extraction
- Enables progressive disclosure in UI/future visualizers

---

## 7. Open Questions & Considerations

### 7.1 To Be Determined
1. **Graph synchronization**: How often to sync SQLite ↔ graph-tool in-memory representation?
2. **LLM caching**: Should we cache LLM responses to reduce costs on re-scans?
3. **Vector embeddings**: Add later for semantic search, or build in from start?
4. **Multi-tenancy**: Single database with project_id, or separate DBs per project?
5. **File watching**: Auto-trigger on file changes, or manual only?

### 7.2 Potential Future Enhancements
- Real-time collaboration (multiple users on same graph)
- Graph versioning and diffing
- Export to common formats (GraphML, GEXF, DOT)
- Web-based visualizer (D3.js, Cytoscape.js)
- Knowledge graph reasoning/inference
- Integration with existing tools (Obsidian, Roam, IDEs)
- Automated summarization at each abstraction level

---

## 8. Success Metrics

### Technical
- API response time under 500ms for standard queries
- Support graphs with 100K+ nodes on consumer hardware
- 99% uptime for local server
- Under 5% LLM API failure rate after retries

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
| LLM costs spiral out of control | High | Token limits, caching, local model fallback, cost tracking |
| graph-tool installation complexity | Medium | Provide Docker, detailed install docs, fallback to NetworkX |
| SQLite performance at scale | Medium | Monitor benchmarks, design for PostgreSQL migration |
| LLM extraction quality varies | High | Configurable prompts, human review workflow, confidence scores |
| File type support insufficient | Medium | Plugin architecture, community contributions |

---

## 10. Next Steps

1. **Review & Refine**: Stakeholder review of requirements
2. **Technical Spikes**: 
   - graph-tool + SQLite integration prototype
   - LLM provider interface design
   - FastAPI async pattern validation
3. **Prioritize Phase 1 Tasks**: Break down into actionable tickets
4. **Set Up Development Environment**: Repo, CI/CD, linting, testing framework
5. **Begin Phase 1 Implementation**

---

*Document Version: 1.0*  
*Last Updated: [Current Date]*  
*Status: Draft for Review*
