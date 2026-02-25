"""Context management for roo-agent.

Provides intelligent context management with two strategies:
1. Truncation - non-destructive sliding window
2. Condensation - AI-powered summarization
"""

from .token_manager import TokenManager
from .manager import ContextManager

__all__ = ["TokenManager", "ContextManager"]
