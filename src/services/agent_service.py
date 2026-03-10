import json
from datetime import datetime
from typing import Optional

import anthropic
from sqlalchemy.orm import Session

from src.config import settings
from src.models.schemas import TodoCreate, TodoUpdate
from src.models.todo import Status
from src.services.todo_service import TodoService

_SNOOZE_TOOL = {
    "name": "snooze_todo",
    "description": "Snooze a todo until a future date/time so it won't surface in reminders until then.",
    "input_schema": {
        "type": "object",
        "properties": {
            "todo_id": {"type": "integer", "description": "The ID of the todo to snooze"},
            "snooze_until": {
                "type": "string",
                "description": "ISO 8601 datetime string for when to resurface this todo",
            },
        },
        "required": ["todo_id", "snooze_until"],
    },
}

_OVERDUE_TOOL = {
    "name": "get_overdue_todos",
    "description": "List todos that are past their due date or haven't been updated in 3+ days.",
    "input_schema": {"type": "object", "properties": {}},
}

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
        "description": "List current todos, optionally filtered by status, priority, or category.",
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
                "category": {
                    "type": "string",
                    "description": "Filter by category",
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
    {
        "name": "update_todo",
        "description": "Update any fields of a todo by its ID (title, description, due_date, status, priority, category, tags).",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "integer", "description": "The ID of the todo to update"},
                "title": {"type": "string", "description": "New title"},
                "description": {"type": "string", "description": "New description"},
                "due_date": {"type": "string", "description": "ISO 8601 datetime string or null to clear"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "done"],
                    "description": "New status",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "New priority",
                },
                "category": {"type": "string", "description": "New category"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New list of tags",
                },
            },
            "required": ["todo_id"],
        },
    },
    {
        "name": "delete_todo",
        "description": "Permanently delete a todo by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todo_id": {"type": "integer", "description": "The ID of the todo to delete"},
            },
            "required": ["todo_id"],
        },
    },
    _SNOOZE_TOOL,
    _OVERDUE_TOOL,
]


class AgentService:
    def __init__(self):
        self.client = (
            anthropic.Anthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )
        self.todo_service = TodoService()

    def chat(self, db: Session, user_message: str, history: Optional[list] = None) -> dict:
        if not self.client:
            return {
                "reply": "AI features are disabled — no Anthropic API key configured.",
                "actions_taken": [],
                "todos_affected": [],
            }

        prior = history or []
        messages = prior + [{"role": "user", "content": user_message}]
        actions_taken: list[str] = []
        todos_affected: list = []

        from src.services.imessage_service import _get_time_context
        system_prompt = (
            f"{_get_time_context()}\n\n"
            "You are a proactive executive assistant managing todos for a busy founder. "
            "Use the provided tools to create, list, complete, snooze, or update todos. "
            "Tasks span sales, engineering, product, fundraising, ops, and personal categories. "
            "When asked what to work on, factor in urgency, due dates, and time of day — "
            "Friday afternoons call for closing loops, Monday mornings for setting direction. "
            "Be direct and brief. No emojis. Plain text only."
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
                category=tool_input.get("category"),
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

        if tool_name == "update_todo":
            todo_id = tool_input["todo_id"]
            fields = {k: v for k, v in tool_input.items() if k != "todo_id"}
            if "due_date" in fields:
                try:
                    fields["due_date"] = datetime.fromisoformat(fields["due_date"]) if fields["due_date"] else None
                except (ValueError, TypeError):
                    fields.pop("due_date")
            updated = self.todo_service.update(db, todo_id, TodoUpdate(**fields))
            if updated:
                actions_taken.append(f"Updated todo ID {todo_id}: '{updated.title}'")
                todos_affected.append(updated)
                return {"success": True}
            return {"success": False, "error": "Todo not found"}

        if tool_name == "delete_todo":
            todo_id = tool_input["todo_id"]
            deleted = self.todo_service.delete(db, todo_id)
            if deleted:
                actions_taken.append(f"Deleted todo ID {todo_id}")
                return {"success": True}
            return {"success": False, "error": "Todo not found"}

        if tool_name == "snooze_todo":
            todo_id = tool_input["todo_id"]
            try:
                snooze_until = datetime.fromisoformat(tool_input["snooze_until"])
            except (ValueError, TypeError):
                return {"success": False, "error": "Invalid snooze_until datetime"}
            from src.models.schemas import TodoUpdate
            updated = self.todo_service.update(db, todo_id, TodoUpdate(snoozed_until=snooze_until))
            if updated:
                actions_taken.append(f"Snoozed todo ID {todo_id} until {snooze_until.isoformat()}")
                return {"success": True}
            return {"success": False, "error": "Todo not found"}

        if tool_name == "get_overdue_todos":
            overdue = self.todo_service.get_overdue(db)
            stale = self.todo_service.get_stale(db)
            result = []
            seen = set()
            for t in overdue:
                seen.add(t.id)
                result.append({"id": t.id, "title": t.title, "due_date": t.due_date.isoformat() if t.due_date else None, "reason": "overdue"})
            for t in stale:
                if t.id not in seen:
                    result.append({"id": t.id, "title": t.title, "updated_at": t.updated_at.isoformat(), "reason": "stale"})
            return result

        return {"success": False, "error": f"Unknown tool: {tool_name}"}
