"""Tool use section — tells the model how to use tools."""

from __future__ import annotations

from typing import Any


def build_tools_section(context: dict[str, Any]) -> str:
    """Build the tool use section with guidelines.

    Tool *definitions* are passed via the native tool-calling mechanism (the
    ``tools`` parameter of chat completions).  This section only provides the
    behavioural instructions that tell the model *how* to work with those
    tools.
    """
    tools = context.get("tools", [])
    if not tools:
        return ""

    return """====

TOOL USE

You have access to a set of tools that are executed upon the user's approval. Use the provider-native tool-calling mechanism. You must call at least one tool per assistant response when working on a task. Prefer calling as many tools as are reasonably needed in a single response to reduce back-and-forth and complete tasks faster.

# Tool Use Guidelines

1. Assess what information you already have and what information you need to proceed with the task.
2. Choose the most appropriate tool based on the task and the tool descriptions provided. Assess if you need additional information to proceed, and which of the available tools would be most effective for gathering this information. For example using the list_files tool is more effective than running a command like `ls` in the terminal. It's critical that you think about each available tool and use the one that best fits the current step in the task.
3. If multiple actions are needed, you may use multiple tools in a single message when appropriate, or use tools iteratively across messages. Each tool use should be informed by the results of previous tool uses. Do not assume the outcome of any tool use. Each step must be informed by the previous step's result.
4. Always read a file before editing it.

By carefully considering the results after tool executions, you can react accordingly and make informed decisions about how to proceed with the task. This iterative process helps ensure the overall success and accuracy of your work."""
