import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.schemas import ChatMessage, ChatResponse, SuccessResponse, TodoRead
from src.models.todo import TodoORM
from src.services.agent_service import AgentService

router = APIRouter(tags=["agent"])
agent_service = AgentService()


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
    )


@router.post("/agent/chat", response_model=SuccessResponse)
def agent_chat(body: ChatMessage, db: Session = Depends(get_db)):
    result = agent_service.chat(db, body.message)
    chat_response = ChatResponse(
        reply=result["reply"],
        actions_taken=result["actions_taken"],
        todos_affected=[_todo_read(t) for t in result["todos_affected"]],
    )
    return SuccessResponse(data=chat_response, message="Agent response generated")
