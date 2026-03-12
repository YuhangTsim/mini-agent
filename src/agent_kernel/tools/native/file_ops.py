"""File operation tools: read_file, write_file, edit_file."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from agent_kernel.tools.base import BaseTool, ToolContext, ToolResult

if TYPE_CHECKING:
    from agent_kernel.tools.permissions import PermissionChecker


def _validate_and_resolve_path(
    path: str,
    working_directory: str,
    agent_role: str,
    permission_checker: "PermissionChecker | None" = None,
) -> str:
    """Resolve path and validate it's within working directory.

    Policy: Block by default, allow override via permission approval.

    Args:
        path: The file path to validate (relative or absolute)
        working_directory: The allowed working directory
        agent_role: The agent role for permission checking
        permission_checker: Optional permission checker for path_traversal policy

    Returns:
        The validated absolute path

    Raises:
        PermissionError: If path escapes working directory without permission
    """
    # Normalize the path - resolve .. and . components
    if os.path.isabs(path):
        full_path = os.path.abspath(path)
    else:
        # First join, then normalize to handle .. and . components
        full_path = os.path.abspath(os.path.join(working_directory, path))

    working_dir_abs = os.path.abspath(working_directory)

    # Check if the normalized path is within working directory
    # Use os.sep to ensure we're checking directory boundaries
    if not (full_path == working_dir_abs or full_path.startswith(working_dir_abs + os.sep)):
        # Path outside working dir - check permission if checker provided
        if permission_checker is not None:
            policy = permission_checker.check_normalized(
                agent_role, "path_traversal", file_path=path
            )
            if policy != "auto_approve":
                raise PermissionError(
                    f"Path '{path}' is outside working directory. "
                    f"Set permission 'path_traversal' to 'auto_approve' to allow."
                )
        else:
            # No permission checker - block by default
            raise PermissionError(
                f"Path '{path}' is outside working directory. "
                f"Set permission 'path_traversal' to 'auto_approve' to allow."
            )

    # Handle symlinks - resolve and validate symlinks within the working directory path
    # Check each component of the path for symlinks, starting from the working directory
    path_parts = full_path.split(os.sep)
    working_parts = working_dir_abs.split(os.sep)

    # Build up the path from the working directory level
    current_path = working_dir_abs

    # Skip the working directory parts and check subsequent components
    for i in range(len(working_parts), len(path_parts)):
        part = path_parts[i]
        if not part:
            continue
        current_path = os.path.join(current_path, part)

        # Only check if the path is within or under the working directory
        if not (
            current_path == working_dir_abs or current_path.startswith(working_dir_abs + os.sep)
        ):
            # Already outside working dir, no need to check further
            break

        # Check if current component is a symlink (only within working directory)
        if os.path.islink(current_path):
            # Resolve the symlink to its real target
            resolved = os.path.realpath(current_path)
            resolved_abs = os.path.abspath(resolved)

            # Check if the resolved path is within working directory
            if not (
                resolved_abs == working_dir_abs or resolved_abs.startswith(working_dir_abs + os.sep)
            ):
                raise PermissionError(f"Symlink points outside working directory: {path}")

    return full_path


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

        try:
            full_path = _validate_and_resolve_path(
                path=path,
                working_directory=context.working_directory,
                agent_role=context.agent_role,
                permission_checker=context.permission_checker,
            )
        except PermissionError as e:
            return ToolResult.failure(str(e))

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

        try:
            full_path = _validate_and_resolve_path(
                path=path,
                working_directory=context.working_directory,
                agent_role=context.agent_role,
                permission_checker=context.permission_checker,
            )
        except PermissionError as e:
            return ToolResult.failure(str(e))

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

        try:
            full_path = _validate_and_resolve_path(
                path=path,
                working_directory=context.working_directory,
                agent_role=context.agent_role,
                permission_checker=context.permission_checker,
            )
        except PermissionError as e:
            return ToolResult.failure(str(e))

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
