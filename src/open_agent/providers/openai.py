"""Deprecated: Use agent_kernel.providers instead."""

import warnings

warnings.warn(
    "open_agent.providers.openai is deprecated. Use agent_kernel.providers.openai instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agent_kernel.providers.openai import *  # noqa: E402,F401,F403
