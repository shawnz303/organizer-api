from unittest.mock import MagicMock, patch

import pytest

from src.models.schemas import TodoCreate
from src.services.agent_service import AgentService
from src.services.todo_service import TodoService


def make_tool_use_response(tool_name: str, tool_input: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.id = "tool_123"
    block.name = tool_name
    block.input = tool_input

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


def make_end_turn_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    block.id = None

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


@pytest.fixture
def mock_anthropic(monkeypatch):
    mock_client = MagicMock()
    monkeypatch.setattr("src.services.agent_service.anthropic.Anthropic", lambda **_: mock_client)
    return mock_client


def test_agent_creates_todo_from_natural_language(mock_anthropic, db_session):
    mock_anthropic.messages.create.side_effect = [
        make_tool_use_response("create_todo", {"title": "Call the doctor", "priority": "high"}),
        make_end_turn_response("I've added 'Call the doctor' as a high priority task."),
    ]

    service = AgentService()
    result = service.chat(db_session, "Remind me to call the doctor urgently")

    assert "Call the doctor" in result["reply"]
    assert len(result["actions_taken"]) == 1
    assert "Created todo" in result["actions_taken"][0]
    assert len(result["todos_affected"]) == 1


def test_agent_lists_todos(mock_anthropic, db_session):
    # Pre-create a todo
    TodoService().create(db_session, TodoCreate(title="Existing task"))

    mock_anthropic.messages.create.side_effect = [
        make_tool_use_response("list_todos", {}),
        make_end_turn_response("You have 1 pending task."),
    ]

    service = AgentService()
    result = service.chat(db_session, "What are my todos?")

    assert "listed" in result["actions_taken"][0].lower()


def test_agent_completes_todo(mock_anthropic, db_session):
    todo = TodoService().create(db_session, TodoCreate(title="Finish report"))

    mock_anthropic.messages.create.side_effect = [
        make_tool_use_response("complete_todo", {"todo_id": todo.id}),
        make_end_turn_response(f"Marked task {todo.id} as done."),
    ]

    service = AgentService()
    result = service.chat(db_session, f"Complete todo {todo.id}")

    assert any("Completed" in a for a in result["actions_taken"])


def test_agent_handles_direct_answer(mock_anthropic, db_session):
    mock_anthropic.messages.create.return_value = make_end_turn_response(
        "I can help you manage your todos!"
    )

    service = AgentService()
    result = service.chat(db_session, "What can you do?")

    assert result["reply"] == "I can help you manage your todos!"
    assert result["actions_taken"] == []


def test_agent_complete_todo_not_found(mock_anthropic, db_session):
    mock_anthropic.messages.create.side_effect = [
        make_tool_use_response("complete_todo", {"todo_id": 99999}),
        make_end_turn_response("Sorry, I couldn't find that todo."),
    ]

    service = AgentService()
    result = service.chat(db_session, "Complete todo 99999")

    assert result["reply"] == "Sorry, I couldn't find that todo."
