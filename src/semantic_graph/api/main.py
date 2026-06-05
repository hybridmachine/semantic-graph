"""FastAPI application entry point."""

import uvicorn
from fastapi import FastAPI

from semantic_graph.api.routes import graph, health, llm, projects

app = FastAPI(title="Semantic Graph Manager", version="0.1.0")

app.include_router(health.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(graph.router, prefix="/api/v1/graph", tags=["graph"])
app.include_router(llm.router, prefix="/api/v1/llm", tags=["llm"])


def start() -> None:
    uvicorn.run("semantic_graph.api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    start()
