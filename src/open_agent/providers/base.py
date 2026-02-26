"""Deprecated: Use agent_kernel.providers instead."""

import warnings

warnings.warn(
    "open_agent.providers.base is deprecated. Use agent_kernel.providers.base instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agent_kernel.providers.base import *  # noqa: E402,F401,F403
