"""File operation tools: read_file, write_file, edit_file."""

from __future__ import annotations

import os
from typing import Any

from agent_kernel.tools.base import BaseTool, ToolContext, ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    groups = ["read"]
    description = (
        "Read a file and return its contents with line numbers. "
        "IMPORTANT: This tool reads exactly one file per call. If you need multiple files, "
        "issue multiple parallel read_file calls.\n\n"
        'Example: { "path": "src/app.py" }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read, relative to the workspace",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path = params["path"]
        full_path = (
            os.path.join(context.working_directory, path) if not os.path.isabs(path) else path
        )

        if not os.path.exists(full_path):
            return ToolResult.failure(f"File not found: {path}")
        if not os.path.isfile(full_path):
            return ToolResult.failure(f"Not a file: {path}")

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            numbered = []
            for i, line in enumerate(lines, 1):
                numbered.append(f"{i:>6}\t{line.rstrip()}")

            content = "\n".join(numbered)
            if len(content) > 100_000:
                content = content[:100_000] + "\n... (truncated)"
            return ToolResult.success(content)
        except Exception as e:
            return ToolResult.failure(f"Error reading file: {e}")


class WriteFileTool(BaseTool):
    name = "write_file"
    groups = ["edit"]
    description = (
        "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. "
        "You MUST provide the COMPLETE file content.\n\n"
        'Example: { "path": "src/app.py", "content": "print(\'hello\')\n" }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to write, relative to the workspace",
            },
            "content": {
                "type": "string",
                "description": "The complete content to write to the file",
            },
        },
        "required": ["path", "content"],
        "additionalProperties": False,
    }

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path = params["path"]
        content = params["content"]
        full_path = (
            os.path.join(context.working_directory, path) if not os.path.isabs(path) else path
        )

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult.success(f"Successfully wrote to {path}")
        except Exception as e:
            return ToolResult.failure(f"Error writing file: {e}")


class EditFileTool(BaseTool):
    name = "edit_file"
    groups = ["edit"]
    description = (
        "Make an exact string replacement in a file. The old_string must match exactly "
        "(including whitespace/indentation). Use this for targeted, surgical edits.\n\n"
        'Example: { "path": "src/app.py", "old_string": "def hello():", "new_string": "def greet():" }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit, relative to the workspace",
            },
            "old_string": {
                "type": "string",
                "description": "The exact string to find and replace (must be unique in the file)",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement string",
            },
        },
        "required": ["path", "old_string", "new_string"],
        "additionalProperties": False,
    }

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path = params["path"]
        old_string = params["old_string"]
        new_string = params["new_string"]
        full_path = (
            os.path.join(context.working_directory, path) if not os.path.isabs(path) else path
        )

        if not os.path.exists(full_path):
            return ToolResult.failure(f"File not found: {path}")

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            count = content.count(old_string)
            if count == 0:
                return ToolResult.failure(f"old_string not found in {path}")
            if count > 1:
                return ToolResult.failure(
                    f"old_string found {count} times in {path}. "
                    "Provide a more specific string with surrounding context."
                )

            new_content = content.replace(old_string, new_string, 1)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return ToolResult.success(f"Successfully edited {path}")
        except Exception as e:
            return ToolResult.failure(f"Error editing file: {e}")
