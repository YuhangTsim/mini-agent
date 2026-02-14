"""Dependency injection helpers."""

from __future__ import annotations

from ...api.service import AgentService


# Global service instance
_service: AgentService | None = None


def set_service(service: AgentService) -> None:
    """Set the global service instance."""
    global _service
    _service = service


def get_service() -> AgentService:
    """Dependency injection for AgentService."""
    if _service is None:
        raise RuntimeError("AgentService not initialized")
    return _service
