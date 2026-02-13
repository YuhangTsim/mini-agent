"""Todo list tool."""

from __future__ import annotations

import json
from typing import Any

from ..base import BaseTool, ToolContext, ToolResult


class UpdateTodoListTool(BaseTool):
    name = "update_todo_list"
    description = (
        "Update the current task's todo/checklist. Provide the full list of items. "
        "Each item has text and a done boolean."
    )
    parameters = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Todo item text"},
                        "done": {"type": "boolean", "description": "Whether the item is done"},
                    },
                    "required": ["text", "done"],
                },
                "description": "The complete list of todo items",
            },
        },
        "required": ["items"],
    }
    always_available = True

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        items = params["items"]
        # Format for display
        lines = []
        for item in items:
            check = "[x]" if item.get("done") else "[ ]"
            lines.append(f"  {check} {item['text']}")

        display = "\n".join(lines) if lines else "(empty todo list)"
        # Return the items as JSON so the caller can persist them
        return ToolResult.success(
            f"Todo list updated:\n{display}\n\n__todo_data__:{json.dumps(items)}"
        )
