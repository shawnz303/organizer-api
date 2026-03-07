import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from src.database import SessionLocal
from src.models.schemas import TodoCreate, TodoUpdate
from src.models.todo import Category, Priority, Status
from src.services.prioritization_service import PrioritizationService
from src.services.reminder_service import get_current_reminders
from src.services.todo_service import TodoService

mcp = FastMCP("organizer-api")

_todo_service = TodoService()
_prioritization_service = PrioritizationService()


def _serialize(todo) -> dict:
    return {
        "id": todo.id,
        "title": todo.title,
        "description": todo.description,
        "due_date": todo.due_date.isoformat() if todo.due_date else None,
        "priority": todo.priority.value if hasattr(todo.priority, "value") else todo.priority,
        "status": todo.status.value if hasattr(todo.status, "value") else todo.status,
        "tags": json.loads(todo.tags or "[]"),
        "category": todo.category.value if todo.category and hasattr(todo.category, "value") else todo.category,
        "created_at": todo.created_at.isoformat(),
        "updated_at": todo.updated_at.isoformat(),
        "last_reminded_at": todo.last_reminded_at.isoformat() if todo.last_reminded_at else None,
    }


@mcp.tool()
def list_todos(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
) -> list[dict]:
    """List all todos. Optionally filter by status (pending/in_progress/done), priority (low/medium/high), or category."""
    db = SessionLocal()
    try:
        todos = _todo_service.list_all(
            db,
            status=Status(status) if status else None,
            priority=Priority(priority) if priority else None,
            category=Category(category) if category else None,
        )
        return [_serialize(t) for t in todos]
    finally:
        db.close()


@mcp.tool()
def create_todo(
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    due_date: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Create a new todo item. due_date should be ISO 8601 format (e.g. 2026-03-15T10:00:00)."""
    from datetime import datetime

    db = SessionLocal()
    try:
        data = TodoCreate(
            title=title,
            description=description,
            priority=Priority(priority),
            due_date=datetime.fromisoformat(due_date) if due_date else None,
            category=Category(category) if category else None,
            tags=tags or [],
        )
        todo = _todo_service.create(db, data)
        return _serialize(todo)
    finally:
        db.close()


@mcp.tool()
def update_todo(
    todo_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Update an existing todo by ID. Only provided fields are changed."""
    from datetime import datetime

    db = SessionLocal()
    try:
        data = TodoUpdate(
            title=title,
            description=description,
            status=Status(status) if status else None,
            priority=Priority(priority) if priority else None,
            due_date=datetime.fromisoformat(due_date) if due_date else None,
            category=Category(category) if category else None,
            tags=tags,
        )
        todo = _todo_service.update(db, todo_id, data)
        if todo is None:
            return {"error": f"Todo {todo_id} not found"}
        return _serialize(todo)
    finally:
        db.close()


@mcp.tool()
def delete_todo(todo_id: int) -> dict:
    """Delete a todo by ID."""
    db = SessionLocal()
    try:
        deleted = _todo_service.delete(db, todo_id)
        if not deleted:
            return {"error": f"Todo {todo_id} not found"}
        return {"deleted": True, "todo_id": todo_id}
    finally:
        db.close()


@mcp.tool()
def get_reminders() -> list[dict]:
    """Get overdue or never-reminded todos that need attention."""
    return get_current_reminders()


@mcp.tool()
def prioritize_todos() -> list[dict]:
    """Use AI to rank all pending todos by urgency and update their priorities."""
    db = SessionLocal()
    try:
        todos = _todo_service.list_all(db, status=Status.pending)
        return _prioritization_service.prioritize(db, todos)
    finally:
        db.close()
