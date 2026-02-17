"""Deprecated: Use agent_kernel.tools.native instead."""

import warnings

warnings.warn(
    "open_agent.tools.native.search is deprecated. Use agent_kernel.tools.native.search instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agent_kernel.tools.native.search import *  # noqa: F401,F403
