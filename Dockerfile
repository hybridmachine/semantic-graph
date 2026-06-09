# ---------------------------------------------------------------------------
# Builder stage — install dependencies and the package
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools
RUN pip install --no-cache-dir hatchling

# Copy only dependency files first for layer caching.
# Create a minimal package tree so pip can resolve and install dependencies
# from pyproject.toml without needing the full source tree.
COPY pyproject.toml README.md ./
RUN mkdir -p src/semantic_graph && touch src/semantic_graph/__init__.py && \
    pip install --no-cache-dir .

# Copy source and install the package
COPY src/ src/
RUN pip install --no-cache-dir --no-deps .

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# ---------------------------------------------------------------------------
# Install graph-tool from the project's Debian repository.
# graph-tool is not available on PyPI; it must be installed via the system
# package manager.  See: https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions
# ---------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg \
    curl \
    && echo "deb [signed-by=/usr/share/keyrings/graph-tool.gpg] https://downloads.skewed.de/apt/bookworm bookworm main" \
       > /etc/apt/sources.list.d/graph_tool.list \
    && curl -fsSL https://downloads.skewed.de/apt/skewed.deb.gpg \
       | gpg --dearmor -o /usr/share/keyrings/graph-tool.gpg \
    && apt-get update && apt-get install -y --no-install-recommends \
       python3-graph-tool \
    && apt-get purge -y gnupg curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Create non-root user
# ---------------------------------------------------------------------------
RUN groupadd --system semanticgraph \
    && useradd --system --no-create-home --gid semanticgraph semanticgraph

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/local/bin /usr/local/bin

# Create data directory with correct ownership
RUN mkdir -p /data && chown semanticgraph:semanticgraph /data

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
LABEL org.opencontainers.image.title="Semantic Graph Manager"
LABEL org.opencontainers.image.description="Extract entities and relationships from data folders using LLM-powered semantic analysis"
LABEL org.opencontainers.image.source="https://github.com/hybridmachine/semantic-graph"
LABEL org.opencontainers.image.licenses="MIT"

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" || exit 1

EXPOSE 8000

USER semanticgraph

ENV SEMANTIC_GRAPH_DATA_DIR=/data
ENV SEMANTIC_GRAPH_API_HOST=0.0.0.0

CMD ["semantic-graph-server"]
