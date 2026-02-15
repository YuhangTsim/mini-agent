"""Command execution tool."""

from __future__ import annotations

import asyncio
from typing import Any

from ..base import BaseTool, ToolContext, ToolResult


class ExecuteCommandTool(BaseTool):
    name = "execute_command"
    description = (
        "Execute a shell command and return its output. Commands run in the working directory "
        "with a timeout. When you need to execute a CLI command, you must provide a clear "
        "explanation of what the command does. Prefer to execute complex CLI commands over "
        "creating executable scripts, since they are more flexible and easier to run.\n\n"
        "Example: { \"command\": \"python -m pytest tests/ -v\" }"
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds. Default: 120.",
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }
    groups = ["command"]

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        command = params["command"]
        timeout = params.get("timeout", 120)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=context.working_directory,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult.failure(f"Command timed out after {timeout}s")

            output_parts = []
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                output_parts.append(f"STDERR:\n{stderr.decode('utf-8', errors='replace')}")

            output = "\n".join(output_parts).strip()
            if len(output) > 100_000:
                output = output[:100_000] + "\n... (truncated)"

            if process.returncode != 0:
                return ToolResult(
                    output=output,
                    error=f"Command exited with code {process.returncode}",
                    is_error=True,
                )

            return ToolResult.success(output or "(no output)")
        except Exception as e:
            return ToolResult.failure(f"Error executing command: {e}")
