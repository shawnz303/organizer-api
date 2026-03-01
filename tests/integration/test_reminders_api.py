import src.services.reminder_service as reminder_module


def test_get_reminders_empty(client):
    reminder_module._overdue_cache = []
    response = client.get("/api/v1/todos/reminders")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == []


def test_get_reminders_with_items(client):
    reminder_module._overdue_cache = [
        {
            "id": 1,
            "title": "Overdue task",
            "due_date": "2026-01-01T00:00:00",
            "status": "pending",
            "priority": "high",
            "reminder_reason": "overdue",
        }
    ]
    response = client.get("/api/v1/todos/reminders")
    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["title"] == "Overdue task"
    assert body["data"][0]["reminder_reason"] == "overdue"
    reminder_module._overdue_cache = []


def test_reminders_route_not_shadowed_by_todo_id(client):
    # Ensure /todos/reminders does NOT return 422 (which would mean it matched /{todo_id})
    reminder_module._overdue_cache = []
    response = client.get("/api/v1/todos/reminders")
    assert response.status_code != 422
    assert response.status_code == 200
