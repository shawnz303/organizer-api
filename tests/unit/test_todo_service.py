import json
from datetime import datetime, timedelta

import pytest

from src.models.schemas import TodoCreate, TodoUpdate
from src.models.todo import Priority, Status
from src.services.todo_service import TodoService


@pytest.fixture
def service():
    return TodoService()


def test_create_todo(db_session, service):
    data = TodoCreate(title="Buy groceries", priority=Priority.high, tags=["personal"])
    todo = service.create(db_session, data)

    assert todo.id is not None
    assert todo.title == "Buy groceries"
    assert todo.priority == Priority.high
    assert todo.status == Status.pending
    assert json.loads(todo.tags) == ["personal"]


def test_get_todo(db_session, service):
    created = service.create(db_session, TodoCreate(title="Task A"))
    fetched = service.get(db_session, created.id)
    assert fetched is not None
    assert fetched.id == created.id


def test_get_nonexistent_todo(db_session, service):
    assert service.get(db_session, 99999) is None


def test_list_todos_with_filter(db_session, service):
    service.create(db_session, TodoCreate(title="High task", priority=Priority.high))
    service.create(db_session, TodoCreate(title="Low task", priority=Priority.low))

    high_todos = service.list_all(db_session, priority=Priority.high)
    assert len(high_todos) == 1
    assert high_todos[0].title == "High task"


def test_update_todo(db_session, service):
    todo = service.create(db_session, TodoCreate(title="Original"))
    updated = service.update(db_session, todo.id, TodoUpdate(title="Updated", priority=Priority.high))

    assert updated is not None
    assert updated.title == "Updated"
    assert updated.priority == Priority.high


def test_update_nonexistent_todo(db_session, service):
    result = service.update(db_session, 99999, TodoUpdate(title="Ghost"))
    assert result is None


def test_delete_todo(db_session, service):
    todo = service.create(db_session, TodoCreate(title="To delete"))
    assert service.delete(db_session, todo.id) is True
    assert service.get(db_session, todo.id) is None


def test_delete_nonexistent_todo(db_session, service):
    assert service.delete(db_session, 99999) is False


def test_get_overdue_todos(db_session, service):
    past_due = datetime.utcnow() - timedelta(days=1)
    future_due = datetime.utcnow() + timedelta(days=1)

    service.create(db_session, TodoCreate(title="Overdue", due_date=past_due))
    service.create(db_session, TodoCreate(title="Not due yet", due_date=future_due))

    overdue = service.get_overdue_or_stale(db_session)
    titles = [t.title for t in overdue]
    assert "Overdue" in titles
    # "Not due yet" may appear since last_reminded_at is NULL


def test_done_todos_excluded_from_overdue(db_session, service):
    past_due = datetime.utcnow() - timedelta(days=1)
    todo = service.create(db_session, TodoCreate(title="Completed overdue", due_date=past_due))
    service.update(db_session, todo.id, TodoUpdate(status=Status.done))

    overdue = service.get_overdue_or_stale(db_session)
    ids = [t.id for t in overdue]
    assert todo.id not in ids


def test_mark_reminded(db_session, service):
    todo = service.create(db_session, TodoCreate(title="Remind me"))
    assert todo.last_reminded_at is None
    service.mark_reminded(db_session, todo.id)
    refreshed = service.get(db_session, todo.id)
    assert refreshed.last_reminded_at is not None
