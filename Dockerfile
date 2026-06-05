# ---------------------------------------------------------------------------
# Builder stage — install dependencies and the package
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools
RUN pip install --no-cache-dir hatchling

# Copy only dependency files first for layer caching
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and install the package
COPY src/ src/
RUN pip install --no-cache-dir --no-deps .

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# TODO: Add graph-tool installation here for production builds.
# graph-tool is not available on PyPI; it must be installed via the system
# package manager or from the official graph-tool Debian/Ubuntu repository.
# See: https://git.skewed.de/count0/graph-tool/-/wikis/installation-instructions

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib /usr/local/lib
COPY --from=builder /usr/local/bin /usr/local/bin

EXPOSE 8000

CMD ["semantic-graph-server"]
