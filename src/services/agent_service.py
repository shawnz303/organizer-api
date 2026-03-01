import json
from datetime import datetime

import anthropic
from sqlalchemy.orm import Session

from src.config import settings
from src.models.schemas import TodoCreate, TodoUpdate
from src.models.todo import Status
from src.services.todo_service import TodoService

TOOLS = [
    {
        "name": "create_todo",
        "description": "Create a new todo item from the user's request.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short title for the task"},
                "description": {"type": "string", "description": "Optional longer description"},
                "due_date": {
                    "type": "string",
                    "description": "ISO 8601 datetime string or null if no due date",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Task priority level",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tags",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_todos",
        "description": "List current todos, optionally filtered by status or priority.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "done"],
                    "description": "Filter by status",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Filter by priority",
                },
            },
        },
    },
    {
        "name": "complete_todo",
        "description": "Mark a todo as done by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "integer", "description": "The ID of the todo to complete"},
            },
            "required": ["todo_id"],
        },
    },
    {
        "name": "update_todo_priority",
        "description": "Update the priority of a specific todo by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "integer", "description": "The ID of the todo to update"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "New priority level",
                },
            },
            "required": ["todo_id", "priority"],
        },
    },
]


class AgentService:
    def __init__(self):
        self.client = (
            anthropic.Anthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )
        self.todo_service = TodoService()

    def chat(self, db: Session, user_message: str) -> dict:
        if not self.client:
            return {
                "reply": "AI features are disabled — no Anthropic API key configured.",
                "actions_taken": [],
                "todos_affected": [],
            }

        messages = [{"role": "user", "content": user_message}]
        actions_taken: list[str] = []
        todos_affected: list = []

        system_prompt = (
            "You are a todo management assistant. Use the provided tools to create, "
            "list, complete, or update todos based on the user's natural language request. "
            "Always confirm what actions you took in a friendly, concise reply. "
            f"Today's date and time is {datetime.utcnow().isoformat()} UTC."
        )

        reply = "Done."
        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                reply = next(
                    (block.text for block in response.content if hasattr(block, "text")),
                    "Done.",
                )
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    result = self._dispatch_tool(
                        db, block.name, block.input, actions_taken, todos_affected
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return {
            "reply": reply,
            "actions_taken": actions_taken,
            "todos_affected": todos_affected,
        }

    def _dispatch_tool(
        self, db: Session, tool_name: str, tool_input: dict, actions_taken: list, todos_affected: list
    ) -> dict:
        if tool_name == "create_todo":
            due_date = tool_input.get("due_date")
            if due_date:
                try:
                    due_date = datetime.fromisoformat(due_date)
                except (ValueError, TypeError):
                    due_date = None
            schema = TodoCreate(
                title=tool_input["title"],
                description=tool_input.get("description"),
                due_date=due_date,
                priority=tool_input.get("priority", "medium"),
                tags=tool_input.get("tags", []),
            )
            todo = self.todo_service.create(db, schema)
            actions_taken.append(f"Created todo: '{todo.title}'")
            todos_affected.append(todo)
            return {"success": True, "todo_id": todo.id, "title": todo.title}

        if tool_name == "list_todos":
            todos = self.todo_service.list_all(
                db,
                status=tool_input.get("status"),
                priority=tool_input.get("priority"),
            )
            actions_taken.append(f"Listed {len(todos)} todos")
            return [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                }
                for t in todos
            ]

        if tool_name == "complete_todo":
            todo_id = tool_input["todo_id"]
            updated = self.todo_service.update(db, todo_id, TodoUpdate(status=Status.done))
            if updated:
                actions_taken.append(f"Completed todo ID {todo_id}: '{updated.title}'")
                todos_affected.append(updated)
                return {"success": True}
            return {"success": False, "error": "Todo not found"}

        if tool_name == "update_todo_priority":
            todo_id = tool_input["todo_id"]
            priority = tool_input["priority"]
            updated = self.todo_service.update(db, todo_id, TodoUpdate(priority=priority))
            if updated:
                actions_taken.append(
                    f"Updated priority of todo {todo_id} to {priority}"
                )
                todos_affected.append(updated)
                return {"success": True}
            return {"success": False, "error": "Todo not found"}

        return {"success": False, "error": f"Unknown tool: {tool_name}"}
