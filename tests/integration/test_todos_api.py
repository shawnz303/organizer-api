def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_todo(client):
    response = client.post(
        "/api/v1/todos",
        json={"title": "Write tests", "priority": "high", "tags": ["dev"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["title"] == "Write tests"
    assert body["data"]["priority"] == "high"
    assert body["data"]["tags"] == ["dev"]


def test_create_todo_missing_title(client):
    response = client.post("/api/v1/todos", json={"priority": "low"})
    assert response.status_code == 422


def test_list_todos(client):
    client.post("/api/v1/todos", json={"title": "Task 1"})
    client.post("/api/v1/todos", json={"title": "Task 2"})
    response = client.get("/api/v1/todos")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert len(body["data"]) == 2


def test_list_todos_filtered_by_priority(client):
    client.post("/api/v1/todos", json={"title": "High task", "priority": "high"})
    client.post("/api/v1/todos", json={"title": "Low task", "priority": "low"})
    response = client.get("/api/v1/todos?priority=high")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["priority"] == "high"


def test_get_todo(client):
    created = client.post("/api/v1/todos", json={"title": "Specific task"}).json()
    todo_id = created["data"]["id"]
    response = client.get(f"/api/v1/todos/{todo_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == todo_id


def test_get_todo_not_found(client):
    response = client.get("/api/v1/todos/99999")
    assert response.status_code == 404


def test_update_todo(client):
    created = client.post("/api/v1/todos", json={"title": "Old title"}).json()
    todo_id = created["data"]["id"]
    response = client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "New title", "status": "in_progress"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "New title"
    assert data["status"] == "in_progress"


def test_update_todo_not_found(client):
    response = client.put("/api/v1/todos/99999", json={"title": "Ghost"})
    assert response.status_code == 404


def test_delete_todo(client):
    created = client.post("/api/v1/todos", json={"title": "To delete"}).json()
    todo_id = created["data"]["id"]
    delete_response = client.delete(f"/api/v1/todos/{todo_id}")
    assert delete_response.status_code == 200
    get_response = client.get(f"/api/v1/todos/{todo_id}")
    assert get_response.status_code == 404


def test_delete_todo_not_found(client):
    response = client.delete("/api/v1/todos/99999")
    assert response.status_code == 404
