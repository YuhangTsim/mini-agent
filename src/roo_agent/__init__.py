"""Roo Agent: A mode-based AI agent framework following Roo Code philosophy.

Usage:
    from roo_agent import Agent, Mode
    
    agent = Agent(mode="coder")
    await agent.run(task, message)
"""

__version__ = "2.0.0"

from .core.agent import Agent
from .core.mode import ModeConfig, get_mode, list_modes

__all__ = ["Agent", "ModeConfig", "get_mode", "list_modes"]
