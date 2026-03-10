from datetime import datetime
from typing import Any, Optional, List

from pydantic import BaseModel, Field

from src.models.todo import Priority, Status, Category


class TodoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Priority = Priority.medium
    status: Status = Status.pending
    tags: List[str] = []
    category: Optional[Category] = None


class TodoUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[Priority] = None
    status: Optional[Status] = None
    tags: Optional[List[str]] = None
    category: Optional[Category] = None
    snoozed_until: Optional[datetime] = None


class TodoRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    due_date: Optional[datetime]
    priority: Priority
    status: Status
    tags: List[str]
    created_at: datetime
    updated_at: datetime
    last_reminded_at: Optional[datetime] = None
    snoozed_until: Optional[datetime] = None
    category: Optional[Category] = None

    model_config = {"from_attributes": True}


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    reply: str
    actions_taken: List[str] = []
    todos_affected: List[TodoRead] = []
