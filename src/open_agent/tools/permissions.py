"""Deprecated: Use agent_kernel.tools instead."""

import warnings

warnings.warn(
    "open_agent.tools.permissions is deprecated. Use agent_kernel.tools.permissions instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from agent_kernel (which now uses duck typing)
from agent_kernel.tools.permissions import PermissionChecker

__all__ = ["PermissionChecker"]
