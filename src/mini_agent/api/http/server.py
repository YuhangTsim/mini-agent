"""FastAPI server for Mini-Agent HTTP API."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from ...config.settings import Settings
from ..service import AgentService
from .dependencies import get_service, set_service
from .middleware import setup_cors
from .routes import approvals, messages, modes, stream, tasks
from .schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle (startup/shutdown)."""
    # Startup
    settings = app.state.settings
    service = AgentService(settings)
    await service.initialize()
    set_service(service)

    yield

    # Shutdown
    service = get_service()
    if service:
        await service.shutdown()


def create_app(settings: Settings, static_dir: str | None = None) -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Mini-Agent API",
        description="HTTP API for Mini-Agent AI framework",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store settings in app state
    app.state.settings = settings

    # Setup middleware
    setup_cors(app)

    # Include routers
    app.include_router(tasks.router)
    app.include_router(messages.router)
    app.include_router(stream.router)
    app.include_router(modes.router)
    app.include_router(approvals.router)

    # Health check endpoint
    @app.get("/api/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(status="ok", version="0.1.0")

    # Serve static frontend if provided
    if static_dir:
        static_path = Path(static_dir)
        if static_path.exists() and static_path.is_dir():
            app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")

    return app


async def run_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    settings: Settings | None = None,
    static_dir: str | None = None,
):
    """Run the FastAPI server with uvicorn."""
    import uvicorn

    if settings is None:
        settings = Settings.load()

    app = create_app(settings, static_dir)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(run_server())
