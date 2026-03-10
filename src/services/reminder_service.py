from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from src.database import SessionLocal
from src.services.todo_service import TodoService


def get_current_reminders() -> list[dict]:
    """Return current overdue and stale todos for the API endpoint."""
    db = SessionLocal()
    try:
        service = TodoService()
        now = __import__("datetime").datetime.utcnow()
        overdue = service.get_overdue(db)
        stale = service.get_stale(db)
        seen = set()
        result = []
        for t in overdue:
            seen.add(t.id)
            result.append({
                "id": t.id, "title": t.title,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "status": t.status, "priority": t.priority,
                "reminder_reason": "overdue",
            })
        for t in stale:
            if t.id not in seen:
                result.append({
                    "id": t.id, "title": t.title,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "status": t.status, "priority": t.priority,
                    "reminder_reason": "stale",
                })
        return result
    finally:
        db.close()


def check_reminders(notify_fn: Optional[Callable[[str], None]] = None) -> None:
    db = SessionLocal()
    try:
        service = TodoService()
        now = datetime.utcnow()

        overdue = service.get_overdue(db)
        stale = service.get_stale(db)

        if notify_fn:
            if overdue:
                lines = ["Overdue:"]
                for t in overdue:
                    due = f" (was due {t.due_date.strftime('%m/%d')})" if t.due_date else ""
                    lines.append(f"• {t.title}{due} [{t.priority}]")
                notify_fn("\n".join(lines))

            if stale:
                lines = ["Haven't touched these in 3+ days:"]
                for t in stale:
                    lines.append(f"• {t.title} [{t.priority}]")
                notify_fn("\n".join(lines))

        for t in overdue + stale:
            service.mark_reminded(db, t.id)
    finally:
        db.close()


def start_scheduler(
    interval_minutes: int = 60,
    notify_fn: Optional[Callable[[str], None]] = None,
) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        check_reminders,
        trigger="interval",
        minutes=interval_minutes,
        kwargs={"notify_fn": notify_fn},
        id="reminder_check",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
