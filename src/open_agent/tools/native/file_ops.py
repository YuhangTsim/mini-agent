"""Deprecated: Use agent_kernel.tools.native instead."""

import warnings

warnings.warn(
    "open_agent.tools.native.file_ops is deprecated. Use agent_kernel.tools.native.file_ops instead.",
    DeprecationWarning,
    stacklevel=2,
)

from agent_kernel.tools.native.file_ops import *  # noqa: F401,F403
