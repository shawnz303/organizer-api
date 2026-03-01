from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.models.schemas import TodoCreate
from src.services.reminder_service import check_reminders, get_current_reminders
from src.services.todo_service import TodoService
import src.services.reminder_service as reminder_module


def test_check_reminders_populates_cache(db_session):
    past_due = datetime.utcnow() - timedelta(hours=2)
    TodoService().create(db_session, TodoCreate(title="Overdue task", due_date=past_due))

    with patch("src.services.reminder_service.SessionLocal", return_value=db_session):
        # Prevent double-close
        db_session.close = lambda: None
        check_reminders()

    cache = get_current_reminders()
    assert len(cache) >= 1
    titles = [item["title"] for item in cache]
    assert "Overdue task" in titles


def test_check_reminders_sets_reason_overdue(db_session):
    past_due = datetime.utcnow() - timedelta(hours=1)
    TodoService().create(db_session, TodoCreate(title="Past due", due_date=past_due))

    with patch("src.services.reminder_service.SessionLocal", return_value=db_session):
        db_session.close = lambda: None
        check_reminders()

    cache = get_current_reminders()
    overdue_items = [c for c in cache if c["title"] == "Past due"]
    assert overdue_items[0]["reminder_reason"] == "overdue"


def test_get_current_reminders_returns_list():
    reminder_module._overdue_cache = [{"id": 1, "title": "Test"}]
    result = get_current_reminders()
    assert result == [{"id": 1, "title": "Test"}]
    reminder_module._overdue_cache = []
