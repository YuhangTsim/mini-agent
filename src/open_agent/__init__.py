"""Open-Agent: Multi-agent AI framework with typed event bus and hierarchical delegation.

Usage:
    from open_agent import Session, Orchestrator
    
    session = Session()
    orchestrator = Orchestrator(session)
    await orchestrator.run("Your task here")
"""

__version__ = "0.1.0"

from .persistence.models import Session
from .core.app import OpenAgentApp as Orchestrator
from .agents.orchestrator import OrchestratorAgent

__all__ = ["Session", "Orchestrator"]
