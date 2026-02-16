"""Approval and user input endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..schemas import ApprovalDecision, InputResponse
from ...service import AgentService
from ..dependencies import get_service


router = APIRouter(tags=["approvals"])


@router.post("/api/approvals/{approval_id}")
async def respond_to_approval(
    approval_id: str,
    data: ApprovalDecision,
    service: AgentService = Depends(get_service),
) -> dict:
    """Respond to a tool approval request.

    Decision must be one of: "y" (allow once), "n" (deny), "always" (always allow).
    """
    await service.resolve_approval(approval_id, data.decision)
    return {"status": "resolved", "approval_id": approval_id, "decision": data.decision}


@router.post("/api/inputs/{input_id}")
async def respond_to_input(
    input_id: str,
    data: InputResponse,
    service: AgentService = Depends(get_service),
) -> dict:
    """Respond to a user input request from the agent."""
    await service.resolve_input(input_id, data.answer)
    return {"status": "resolved", "input_id": input_id}
