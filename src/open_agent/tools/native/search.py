"""Search tools: search_files, list_files."""

from __future__ import annotations

import fnmatch
import os
import re
from typing import Any

from open_agent.tools.base import BaseTool, ToolContext, ToolResult


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = (
        "Search for a regex pattern across files in a directory. "
        "Returns matching lines with file paths and line numbers.\n\n"
        'Example: { "path": "src", "pattern": "def main", "glob": "*.py" }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The directory to search in, relative to the workspace",
            },
            "pattern": {
                "type": "string",
                "description": "The regex pattern to search for",
            },
            "glob": {
                "type": "string",
                "description": "File glob pattern to filter (e.g., '*.py'). Default: all files.",
            },
        },
        "required": ["path", "pattern", "glob"],
        "additionalProperties": False,
    }

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        search_path = params["path"]
        pattern = params["pattern"]
        glob_pattern = params.get("glob", "*")

        full_path = (
            os.path.join(context.working_directory, search_path)
            if not os.path.isabs(search_path)
            else search_path
        )

        if not os.path.exists(full_path):
            return ToolResult.failure(f"Path not found: {search_path}")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return ToolResult.failure(f"Invalid regex pattern: {e}")

        matches = []
        max_matches = 200

        for root, _dirs, files in os.walk(full_path):
            _dirs[:] = [
                d
                for d in _dirs
                if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git")
            ]

            for filename in files:
                if not fnmatch.fnmatch(filename, glob_pattern):
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, context.working_directory)

                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append(f"{rel_path}:{line_num}: {line.rstrip()}")
                                if len(matches) >= max_matches:
                                    break
                except (PermissionError, IsADirectoryError):
                    continue

                if len(matches) >= max_matches:
                    break
            if len(matches) >= max_matches:
                break

        if not matches:
            return ToolResult.success(f"No matches found for pattern '{pattern}' in {search_path}")

        result = "\n".join(matches)
        if len(matches) >= max_matches:
            result += f"\n... (showing first {max_matches} matches)"
        return ToolResult.success(result)


class ListFilesTool(BaseTool):
    name = "list_files"
    description = (
        "List files and directories at the given path. Use recursive=true to see the full tree.\n\n"
        'Example: { "path": ".", "recursive": true }'
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The directory path to list, relative to the workspace",
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to list recursively. Default: false.",
            },
        },
        "required": ["path", "recursive"],
        "additionalProperties": False,
    }

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path = params["path"]
        recursive = params.get("recursive", False)

        full_path = (
            os.path.join(context.working_directory, path) if not os.path.isabs(path) else path
        )

        if not os.path.exists(full_path):
            return ToolResult.failure(f"Path not found: {path}")
        if not os.path.isdir(full_path):
            return ToolResult.failure(f"Not a directory: {path}")

        entries = []
        max_entries = 500

        if recursive:
            for root, dirs, files in os.walk(full_path):
                dirs[:] = [
                    d
                    for d in sorted(dirs)
                    if not d.startswith(".") and d not in ("node_modules", "__pycache__")
                ]
                level = root.replace(full_path, "").count(os.sep)
                indent = "  " * level
                dirname = os.path.basename(root)
                if level > 0:
                    entries.append(f"{indent}{dirname}/")
                for f in sorted(files):
                    if not f.startswith("."):
                        entries.append(f"{indent}  {f}")
                if len(entries) >= max_entries:
                    entries.append("... (truncated)")
                    break
        else:
            items = sorted(os.listdir(full_path))
            for item in items:
                item_path = os.path.join(full_path, item)
                suffix = "/" if os.path.isdir(item_path) else ""
                entries.append(f"{item}{suffix}")

        return ToolResult.success("\n".join(entries) if entries else "(empty directory)")
