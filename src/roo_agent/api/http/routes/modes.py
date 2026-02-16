"""Mode management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..schemas import ModeListResponse, ModeResponse
from ...service import AgentService
from ..dependencies import get_service


router = APIRouter(prefix="/api/modes", tags=["modes"])


@router.get("", response_model=ModeListResponse)
async def list_modes(
    service: AgentService = Depends(get_service),
) -> ModeListResponse:
    """List all available modes."""
    modes = service.get_modes()
    return ModeListResponse(
        modes=[
            ModeResponse(
                slug=mode.slug,
                name=mode.name,
                when_to_use=mode.when_to_use,
                tool_groups=mode.tool_groups,
            )
            for mode in modes
        ]
    )
