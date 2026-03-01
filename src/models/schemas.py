from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.models.todo import Priority, Status


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    due_date: datetime | None = None
    priority: Priority = Priority.medium
    status: Status = Status.pending
    tags: list[str] = []


class TodoUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    due_date: datetime | None = None
    priority: Priority | None = None
    status: Status | None = None
    tags: list[str] | None = None


class TodoRead(BaseModel):
    id: int
    title: str
    description: str | None
    due_date: datetime | None
    priority: Priority
    status: Status
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    last_reminded_at: datetime | None

    model_config = {"from_attributes": True}


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    actions_taken: list[str] = []
    todos_affected: list[TodoRead] = []
