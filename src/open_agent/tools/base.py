"""Deprecated: Use agent_kernel.tools instead."""

import warnings

warnings.warn(
    "open_agent.tools.base is deprecated. Use agent_kernel.tools.base instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agent_kernel.tools.base import *  # noqa: F401,F403
