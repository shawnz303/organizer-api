import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.schemas import SuccessResponse, TodoCreate, TodoRead, TodoUpdate
from src.models.todo import Category, Priority, Status, TodoORM
from src.services.category_service import CategoryService
from src.services.todo_service import TodoService

router = APIRouter(tags=["todos"])
service = TodoService()
category_service = CategoryService()


def _todo_read(todo: TodoORM) -> TodoRead:
    return TodoRead(
        id=todo.id,
        title=todo.title,
        description=todo.description,
        due_date=todo.due_date,
        priority=todo.priority,
        status=todo.status,
        tags=json.loads(todo.tags or "[]"),
        created_at=todo.created_at,
        updated_at=todo.updated_at,
        last_reminded_at=todo.last_reminded_at,
        category=todo.category,
    )


@router.get("/todos", response_model=SuccessResponse)
def list_todos(
    status: Optional[Status] = Query(None),
    priority: Optional[Priority] = Query(None),
    category: Optional[Category] = Query(None),
    db: Session = Depends(get_db),
):
    todos = service.list_all(db, status=status, priority=priority, category=category)
    return SuccessResponse(
        data=[_todo_read(t) for t in todos],
        message=f"Retrieved {len(todos)} todos",
    )


@router.post("/todos", response_model=SuccessResponse, status_code=201)
def create_todo(data: TodoCreate, db: Session = Depends(get_db)):
    todo = service.create(db, data)
    return SuccessResponse(data=_todo_read(todo), message="Todo created successfully")


@router.get("/todos/categories", response_model=SuccessResponse)
def get_todos_by_category(db: Session = Depends(get_db)):
    results = category_service.analyze(db)
    return SuccessResponse(
        data=results,
        message=f"Analysis for {len(results)} categories",
    )


@router.get("/todos/{todo_id}", response_model=SuccessResponse)
def get_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = service.get(db, todo_id)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return SuccessResponse(data=_todo_read(todo), message="Todo retrieved")


@router.put("/todos/{todo_id}", response_model=SuccessResponse)
def update_todo(todo_id: int, data: TodoUpdate, db: Session = Depends(get_db)):
    todo = service.update(db, todo_id, data)
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    return SuccessResponse(data=_todo_read(todo), message="Todo updated")


@router.delete("/todos/{todo_id}", response_model=SuccessResponse)
def delete_todo(todo_id: int, db: Session = Depends(get_db)):
    deleted = service.delete(db, todo_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Todo not found")
    return SuccessResponse(data=None, message="Todo deleted")
