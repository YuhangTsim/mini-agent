"""File operation tools: read_file, write_file, edit_file."""

from __future__ import annotations

import os
from typing import Any

from ..base import BaseTool, ToolContext, ToolResult


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file at the given path. Returns the file content with line numbers."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to read (relative to working directory or absolute)",
            },
        },
        "required": ["path"],
    }
    groups = ["read"]

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path = params["path"]
        full_path = os.path.join(context.working_directory, path) if not os.path.isabs(path) else path

        if not os.path.exists(full_path):
            return ToolResult.failure(f"File not found: {path}")
        if not os.path.isfile(full_path):
            return ToolResult.failure(f"Not a file: {path}")

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            # Add line numbers
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
    description = "Write content to a file. Creates the file if it doesn't exist, overwrites if it does."
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to write (relative to working directory or absolute)",
            },
            "content": {
                "type": "string",
                "description": "The content to write to the file",
            },
        },
        "required": ["path", "content"],
    }
    groups = ["edit"]

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path = params["path"]
        content = params["content"]
        full_path = os.path.join(context.working_directory, path) if not os.path.isabs(path) else path

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult.success(f"Successfully wrote to {path}")
        except Exception as e:
            return ToolResult.failure(f"Error writing file: {e}")


class EditFileTool(BaseTool):
    name = "edit_file"
    description = (
        "Make an exact string replacement in a file. The old_string must match exactly "
        "(including whitespace/indentation). Use this for targeted edits."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "The exact string to find and replace",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement string",
            },
        },
        "required": ["path", "old_string", "new_string"],
    }
    groups = ["edit"]

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path = params["path"]
        old_string = params["old_string"]
        new_string = params["new_string"]
        full_path = os.path.join(context.working_directory, path) if not os.path.isabs(path) else path

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
