import json
from unittest.mock import MagicMock, patch

import pytest

from src.models.schemas import TodoCreate
from src.models.todo import Category, Status
from src.services.category_service import CategoryService
from src.services.todo_service import TodoService


def make_claude_response(payload: dict):
    block = MagicMock()
    block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [block]
    return response


@pytest.fixture
def mock_anthropic(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr(
        "src.services.category_service.anthropic.Anthropic", lambda **_: mock_client
    )
    return mock_client


def test_analyze_returns_empty_when_no_todos(mock_anthropic, db_session):
    service = CategoryService()
    assert service.analyze(db_session) == []


def test_analyze_returns_empty_when_all_done(mock_anthropic, db_session):
    TodoService().create(
        db_session,
        TodoCreate(title="Done task", status=Status.done, category=Category.engineering),
    )
    service = CategoryService()
    assert service.analyze(db_session) == []


def test_analyze_single_task_skips_claude_call(mock_anthropic, db_session):
    TodoService().create(
        db_session,
        TodoCreate(title="Solo task", category=Category.sales),
    )
    service = CategoryService()
    results = service.analyze(db_session)

    mock_anthropic.messages.create.assert_not_called()
    assert len(results) == 1
    assert results[0]["category"] == "sales"
    assert results[0]["commonalities"] == "Single task in this category."
    assert "Solo task" in results[0]["strategy"]


def test_analyze_calls_claude_for_multiple_tasks(mock_anthropic, db_session):
    mock_anthropic.messages.create.return_value = make_claude_response(
        {
            "commonalities": "Both require backend access.",
            "strategy": "Tackle them in a single engineering sprint.",
        }
    )

    todo_svc = TodoService()
    todo_svc.create(db_session, TodoCreate(title="Fix auth bug", category=Category.engineering))
    todo_svc.create(db_session, TodoCreate(title="Add API endpoint", category=Category.engineering))

    service = CategoryService()
    results = service.analyze(db_session)

    assert len(results) == 1
    assert results[0]["category"] == "engineering"
    assert results[0]["commonalities"] == "Both require backend access."
    assert results[0]["strategy"] == "Tackle them in a single engineering sprint."
    assert len(results[0]["tasks"]) == 2
    mock_anthropic.messages.create.assert_called_once()


def test_analyze_groups_multiple_categories(mock_anthropic, db_session):
    mock_anthropic.messages.create.return_value = make_claude_response(
        {"commonalities": "Shared theme.", "strategy": "Group strategy."}
    )

    todo_svc = TodoService()
    todo_svc.create(db_session, TodoCreate(title="Sales call", category=Category.sales))
    todo_svc.create(db_session, TodoCreate(title="Cold outreach", category=Category.sales))
    todo_svc.create(db_session, TodoCreate(title="Build feature", category=Category.engineering))

    service = CategoryService()
    results = service.analyze(db_session)

    categories = [r["category"] for r in results]
    assert "sales" in categories
    assert "engineering" in categories


def test_analyze_uncategorized_tasks(mock_anthropic, db_session):
    TodoService().create(db_session, TodoCreate(title="Misc task"))

    service = CategoryService()
    results = service.analyze(db_session)

    assert results[0]["category"] == "uncategorized"


def test_analyze_no_api_key(monkeypatch, db_session):
    monkeypatch.setattr("src.services.category_service.settings.anthropic_api_key", None)

    TodoService().create(db_session, TodoCreate(title="Task A", category=Category.ops))
    TodoService().create(db_session, TodoCreate(title="Task B", category=Category.ops))

    service = CategoryService()
    results = service.analyze(db_session)

    assert results[0]["commonalities"] == "AI unavailable."
    assert results[0]["strategy"] == "No API key configured."
