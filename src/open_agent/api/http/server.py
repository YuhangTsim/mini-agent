"""FastAPI HTTP server for open-agent."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from open_agent.api.service import AgentService
from open_agent.config import Settings


class MessageRequest(BaseModel):
    message: str
    agent_role: str | None = None


class ApprovalRequest(BaseModel):
    response: str  # "approved" or "denied"


class InputRequest(BaseModel):
    response: str


# Global service instance
_service: AgentService | None = None


async def get_service() -> AgentService:
    """Get or initialize the global service."""
    global _service
    if _service is None:
        settings = Settings.load()
        _service = AgentService(settings)
        await _service.initialize()
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Manage service lifecycle."""
    # Startup
    await get_service()
    yield
    # Shutdown
    global _service
    if _service:
        await _service.shutdown()


app = FastAPI(title="Open Agent API", lifespan=lifespan)


@app.post("/api/send")
async def send_message(request: MessageRequest) -> dict:
    """Send a message and get response."""
    service = await get_service()
    try:
        result = await service.send_message(
            message=request.message,
            agent_role=request.agent_role,
        )
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/approvals/{approval_id}")
async def resolve_approval(approval_id: str, request: ApprovalRequest) -> dict:
    """Resolve a pending tool approval."""
    service = await get_service()
    await service.resolve_approval(approval_id, request.response)
    return {"status": "ok"}


@app.post("/api/inputs/{input_id}")
async def resolve_input(input_id: str, request: InputRequest) -> dict:
    """Resolve a pending user input request."""
    service = await get_service()
    await service.resolve_input(input_id, request.response)
    return {"status": "ok"}


@app.get("/api/stream")
async def stream_events() -> StreamingResponse:
    """Stream events via SSE."""
    service = await get_service()
    
    async def event_generator():
        queue = service.event_bus.stream(None)  # Wildcard stream
        try:
            while True:
                try:
                    # Use asyncio.wait_for to allow checking for client disconnect
                    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"event: {payload.event}\n"
                    yield f"data: {payload.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            service.event_bus.unstream(queue, None)
            raise
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
