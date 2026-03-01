from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models.schemas import SuccessResponse
from src.services.prioritization_service import PrioritizationService
from src.services.reminder_service import get_current_reminders
from src.services.todo_service import TodoService

router = APIRouter(tags=["reminders"])


@router.get("/todos/reminders", response_model=SuccessResponse)
def get_reminders():
    reminders = get_current_reminders()
    return SuccessResponse(
        data=reminders,
        message=f"{len(reminders)} overdue or stale todos",
    )


@router.post("/todos/prioritize", response_model=SuccessResponse)
def prioritize_todos(db: Session = Depends(get_db)):
    todos = TodoService().list_all(db)
    ranked = PrioritizationService().prioritize(db, todos)
    return SuccessResponse(data=ranked, message="Todos prioritized by AI")
