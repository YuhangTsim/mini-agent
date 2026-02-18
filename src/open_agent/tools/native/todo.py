"""Todo list tools for tracking multi-step tasks.

Following the opencode philosophy:
- Use todos for complex multi-step tasks (3+ steps)
- Skip for simple one-step tasks
- Real-time status updates
- Session-scoped persistence
"""

from __future__ import annotations

import json
from typing import Any

from agent_kernel.tools.base import BaseTool, ToolContext, ToolResult


TODO_WRITE_DESCRIPTION = """Use this tool to create and manage a structured task list for your current coding session. This helps you track progress, organize complex tasks, and demonstrate thoroughness to the user.
It also helps the user understand the progress of the task and overall progress of their requests.

## When to Use This Tool

Use this tool proactively in these scenarios:

1. **Complex multistep tasks** - When a task requires 3 or more distinct steps or actions
2. **Non-trivial and complex tasks** - Tasks that require careful planning or multiple operations
3. **User explicitly requests todo list** - When the user directly asks you to use the todo list
4. **User provides multiple tasks** - When users provide a list of things to be done (numbered or comma-separated)
5. **After receiving new instructions** - Immediately capture user requirements as todos. Feel free to edit the todo list based on new information.
6. **After completing a task** - Mark it complete and add any new follow-up tasks
7. **When you start working on a new task, mark the todo as in_progress.** Ideally you should only have one todo as in_progress at a time. Complete existing tasks before starting new ones.

## When NOT to Use This Tool

Skip using this tool when:
1. There is only a single, straightforward task
2. The task is trivial and tracking it provides no organizational benefit
3. The task can be completed in less than 3 trivial steps
4. The task is purely conversational or informational

NOTE that you should not use this tool if there is only one trivial task to do. In this case you are better off just doing the task directly.

## Examples of When to Use the Todo List

**Example 1: Multi-step feature implementation**
User: I want to add a dark mode toggle to the application settings. Make sure you run the tests and build when you're done!
Assistant: I'll help add a dark mode toggle to your application settings. Let me create a todo list to track this implementation.
*Creates todo list with the following items:*
1. Create dark mode toggle component in Settings page
2. Add dark mode state management (context/store)
3. Implement CSS-in-JS styles for dark theme
4. Update existing components to support theme switching
5. Run tests and build process, addressing any failures or errors that occur

**Example 2: Refactoring across multiple files**
User: Help me rename the function getCwd to getCurrentWorkingDirectory across my project
Assistant: Let me first search through your codebase to find all occurrences of 'getCwd'.
*Uses grep or search tools to locate all instances*
Assistant: I've found 15 instances of 'getCwd' across 8 different files. Let me create a todo list to track these changes.
*Creates todo list with specific items for each file that needs updating*

**Example 3: Multiple features**
User: I need to implement these features for my e-commerce site: user registration, product catalog, shopping cart, and checkout flow.
Assistant: I'll help implement these features. First, let's add all the features to the todo list.
*Creates a todo list breaking down each feature into specific tasks*

## Examples of When NOT to Use the Todo List

**Example 1: Simple question**
User: How do I print 'Hello World' in Python?
Assistant: In Python, you can print "Hello World" with: print("Hello World")
*No todo list needed - single trivial task*

**Example 2: Informational request**
User: What does the git status command do?
Assistant: The git status command shows the current state of your working directory...
*No todo list needed - just an explanation*

**Example 3: Single code change**
User: Can you add a comment to the calculateTotal function?
Assistant: Sure, let me add a comment to explain what it does.
*Uses Edit tool directly - no todo needed*

## Task States and Management

1. **Task States**: Use these states to track progress:
   - `pending`: Task not yet started
   - `in_progress`: Currently working on (limit to ONE task at a time)
   - `completed`: Task finished successfully
   - `cancelled`: Task no longer needed

2. **Task Management**:
   - Update task status in real-time as you work
   - Mark tasks complete IMMEDIATELY after finishing (don't batch completions)
   - Only have ONE task in_progress at any time
   - Complete current tasks before starting new ones
   - Cancel tasks that become irrelevant

3. **Priority Levels**:
   - `high`: Critical path, blocking other work
   - `medium`: Normal priority (default)
   - `low`: Nice to have, can be deferred

4. **Task Breakdown**:
   - Create specific, actionable items
   - Break complex tasks into smaller, manageable steps
   - Use clear, descriptive task names

When in doubt, use this tool. Being proactive with task management demonstrates attentiveness and ensures you complete all requirements successfully.
"""


class TodoWriteTool(BaseTool):
    """Write/replace the entire todo list for the current session."""

    name = "todo_write"
    description = TODO_WRITE_DESCRIPTION
    parameters = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "The complete todo list to replace the current one. Each item should have id, content, status, and priority.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique identifier for the todo item. Use existing IDs for updates, new UUID for new items.",
                        },
                        "content": {
                            "type": "string",
                            "description": "Brief description of the task",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                            "description": "Current status of the task",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Priority level of the task",
                            "default": "medium",
                        },
                    },
                    "required": ["id", "content", "status", "priority"],
                },
            },
        },
        "required": ["todos"],
    }
    category = "native"
    skip_approval = True  # Internal state management

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        from open_agent.persistence.models import TodoItem
        from open_agent.persistence.store import Store
        from open_agent.bus import EventBus
        from open_agent.bus.events import Event

        # Get the store and event bus from context
        # We need to access these via the app context, but for now we'll use a simple approach
        # The tools will be called from SessionProcessor which has access to store and bus

        todo_data = params.get("todos", [])

        # Convert to TodoItem objects
        todos = []
        for item in todo_data:
            todo = TodoItem(
                id=item.get("id", ""),
                content=item.get("content", ""),
                status=item.get("status", "pending"),
                priority=item.get("priority", "medium"),
                session_id=context.session_id,
            )
            todos.append(todo)

        # Format for display
        lines = []
        pending_count = 0
        in_progress_count = 0
        completed_count = 0
        cancelled_count = 0

        for todo in todos:
            if todo.status == "pending":
                symbol = "[ ]"
                pending_count += 1
            elif todo.status == "in_progress":
                symbol = "[→]"
                in_progress_count += 1
            elif todo.status == "completed":
                symbol = "[✓]"
                completed_count += 1
            elif todo.status == "cancelled":
                symbol = "[✗]"
                cancelled_count += 1
            else:
                symbol = "[?]"

            priority_indicator = ""
            if todo.priority == "high":
                priority_indicator = " (!)"
            elif todo.priority == "low":
                priority_indicator = " (↓)"

            lines.append(f"  {symbol} {todo.content}{priority_indicator}")

        display = "\n".join(lines) if lines else "(empty todo list)"

        summary_parts = []
        if completed_count:
            summary_parts.append(f"{completed_count} completed")
        if in_progress_count:
            summary_parts.append(f"{in_progress_count} in progress")
        if pending_count:
            summary_parts.append(f"{pending_count} pending")
        if cancelled_count:
            summary_parts.append(f"{cancelled_count} cancelled")

        summary = f"Todo list updated ({', '.join(summary_parts) if summary_parts else 'empty'}):"

        # Return summary with todos embedded in output for the session processor
        # The output format is parsed by SessionProcessor._handle_todo_write
        return ToolResult.success(
            f"{summary}\n{display}\n\n__todo_data__:{json.dumps([t.to_row() for t in todos])}"
        )


class TodoReadTool(BaseTool):
    """Read the current todo list for the session."""

    name = "todo_read"
    description = (
        "Read the current todo list for this session. "
        "Use this tool proactively to check what tasks are pending or in progress. "
        "Call this at the beginning of conversations, before starting new tasks, "
        "and after completing work to stay aligned with the overall plan."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "description": "No parameters needed - reads the current session's todo list",
    }
    category = "native"
    skip_approval = True  # Internal state management

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        # The actual reading happens in SessionProcessor which has access to the store
        # This tool just signals intent - the processor will inject current todos into context
        return ToolResult.success(
            "Reading current todo list..."
        )
