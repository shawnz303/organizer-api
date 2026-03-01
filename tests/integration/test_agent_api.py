from unittest.mock import MagicMock


def make_end_turn_response(text: str):
    block = MagicMock()
    block.type = "text"
    block.text = text
    block.id = None
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def make_tool_use_response(tool_name: str, tool_input: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.id = "tool_abc"
    block.name = tool_name
    block.input = tool_input
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response


def test_agent_chat_creates_todo(client, monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        make_tool_use_response("create_todo", {"title": "Buy milk", "priority": "low"}),
        make_end_turn_response("Added 'Buy milk' to your list."),
    ]
    monkeypatch.setattr("src.services.agent_service.anthropic.Anthropic", lambda **_: mock_client)

    # Re-initialize agent service with patched client
    import src.api.agent as agent_module
    from src.services.agent_service import AgentService
    agent_module.agent_service = AgentService()

    response = client.post("/api/v1/agent/chat", json={"message": "Add buy milk as low priority"})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "Added" in body["data"]["reply"]
    assert len(body["data"]["actions_taken"]) == 1
    assert len(body["data"]["todos_affected"]) == 1


def test_agent_chat_empty_message(client):
    response = client.post("/api/v1/agent/chat", json={"message": ""})
    assert response.status_code == 422


def test_agent_chat_direct_answer(client, monkeypatch):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = make_end_turn_response(
        "I can help you manage todos!"
    )
    monkeypatch.setattr("src.services.agent_service.anthropic.Anthropic", lambda **_: mock_client)

    import src.api.agent as agent_module
    from src.services.agent_service import AgentService
    agent_module.agent_service = AgentService()

    response = client.post("/api/v1/agent/chat", json={"message": "What can you do?"})
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["actions_taken"] == []
