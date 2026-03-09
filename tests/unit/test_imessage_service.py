from unittest.mock import MagicMock, patch

import pytest

from src.models.todo import Category


def make_claude_response(text: str):
    block = MagicMock()
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


@patch("src.services.imessage_service.anthropic.Anthropic")
@patch("src.services.imessage_service.settings")
def test_expand_todo_description_returns_text(mock_settings, mock_anthropic_cls):
    mock_settings.anthropic_api_key = "test-key"
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = make_claude_response("Step 1: do the thing. Step 2: verify it works.")

    from src.services.imessage_service import _expand_todo_description
    result = _expand_todo_description("launch marketing campaign")

    assert "Step 1" in result
    mock_client.messages.create.assert_called_once()


@patch("src.services.imessage_service.anthropic.Anthropic")
@patch("src.services.imessage_service.settings")
def test_expand_todo_description_skips_without_api_key(mock_settings, mock_anthropic_cls):
    mock_settings.anthropic_api_key = None

    from src.services.imessage_service import _expand_todo_description
    result = _expand_todo_description("some task")

    assert result is None
    mock_anthropic_cls.assert_not_called()


@patch("src.services.imessage_service._expand_todo_description")
@patch("src.services.imessage_service.SessionLocal")
@patch("src.services.imessage_service.settings")
def test_create_todo_stores_description(mock_settings, mock_session_local, mock_expand, db_session):
    mock_settings.anthropic_api_key = "test-key"
    mock_expand.return_value = "Detailed plan here."
    mock_session_local.return_value = db_session

    from src.services.imessage_service import _create_todo_from_text
    result = _create_todo_from_text("fix login bug")

    assert result.startswith("Created: fix login bug")
    mock_expand.assert_called_once_with("fix login bug")

    from src.services.todo_service import TodoService
    todos = TodoService().list_all(db_session)
    assert any(t.description == "Detailed plan here." for t in todos)


@patch("src.services.imessage_service._expand_todo_description")
@patch("src.services.imessage_service.SessionLocal")
@patch("src.services.imessage_service.settings")
def test_create_todo_sms_reply_is_headline_only(mock_settings, mock_session_local, mock_expand, db_session):
    mock_settings.anthropic_api_key = "test-key"
    mock_expand.return_value = "Very long detailed plan that should not appear in SMS."
    mock_session_local.return_value = db_session

    from src.services.imessage_service import _create_todo_from_text
    result = _create_todo_from_text("ship new feature", category=Category.engineering)

    assert "Very long detailed plan" not in result
    assert "ship new feature" in result
    assert "[engineering]" in result


@patch("src.services.imessage_service._expand_todo_description")
@patch("src.services.imessage_service.SessionLocal")
@patch("src.services.imessage_service.settings")
def test_get_todo_list_text_headline_only(mock_settings, mock_session_local, mock_expand, db_session):
    mock_settings.anthropic_api_key = "test-key"
    mock_expand.return_value = "Detailed plan that should not appear in SMS list."
    mock_session_local.return_value = db_session

    from src.services.imessage_service import _create_todo_from_text, _get_todo_list_text
    _create_todo_from_text("task one", category=Category.sales)

    mock_session_local.return_value = db_session
    result = _get_todo_list_text()

    assert "Detailed plan" not in result
    assert "task one" in result
