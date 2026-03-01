from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from src.database import SessionLocal
from src.services.todo_service import TodoService

_overdue_cache: list[dict] = []


def check_reminders() -> None:
    global _overdue_cache
    db = SessionLocal()
    try:
        service = TodoService()
        overdue = service.get_overdue_or_stale(db)
        now = datetime.utcnow()
        _overdue_cache = [
            {
                "id": t.id,
                "title": t.title,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "status": t.status,
                "priority": t.priority,
                "reminder_reason": (
                    "overdue" if t.due_date and t.due_date < now else "never_reminded"
                ),
            }
            for t in overdue
        ]
        for t in overdue:
            service.mark_reminded(db, t.id)
    finally:
        db.close()


def get_current_reminders() -> list[dict]:
    return _overdue_cache


def start_scheduler(interval_minutes: int = 60) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_reminders,
        trigger="interval",
        minutes=interval_minutes,
        id="reminder_check",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
