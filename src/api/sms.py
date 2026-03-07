import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import PlainTextResponse

from src.database import SessionLocal
from src.models.schemas import TodoCreate
from src.models.todo import Priority, Status
from src.services.sms_service import send_sms
from src.services.todo_service import TodoService

router = APIRouter(tags=["sms"])

HELP_TEXT = (
    "Commands:\n"
    "R: <title> [Mon/Tue/...] - create reminder\n"
    "LIST - list pending todos\n"
    "DONE <id> - mark todo done\n"
    "HELP - show this message"
)

_DAY_NAMES = {
    "mon": 0, "monday": 0,
    "tue": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}


def _parse_due_date(text: str) -> tuple[str, datetime | None]:
    """Extract a day name from the end of text and return (cleaned_title, due_date)."""
    words = text.strip().split()
    if words:
        last = words[-1].lower().rstrip(".,")
        if last in _DAY_NAMES:
            today = datetime.utcnow()
            target_weekday = _DAY_NAMES[last]
            days_ahead = (target_weekday - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            due = (today + timedelta(days=days_ahead)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            title = " ".join(words[:-1]).strip() or text.strip()
            return title, due
    return text.strip(), None


def _twiml_response(message: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{message}</Message></Response>'
    return Response(content=xml, media_type="application/xml")


@router.post("/sms/webhook")
async def sms_webhook(
    Body: str = Form(""),
    From: str = Form(""),
):
    text = Body.strip()
    upper = text.upper()
    db = SessionLocal()
    service = TodoService()

    try:
        # HELP
        if upper in ("HELP", "H", "?"):
            return _twiml_response(HELP_TEXT)

        # LIST
        if upper in ("LIST", "L", "LS"):
            todos = service.list_all(db, status=Status.pending)
            if not todos:
                return _twiml_response("No pending todos.")
            lines = [f"#{t.id} [{t.priority.value}] {t.title}" + (f" (due {t.due_date.strftime('%a %b %d')})" if t.due_date else "") for t in todos[:10]]
            return _twiml_response("\n".join(lines))

        # DONE <id>
        done_match = re.match(r"^(?:DONE|D|COMPLETE)\s+(\d+)$", upper)
        if done_match:
            todo_id = int(done_match.group(1))
            from src.models.schemas import TodoUpdate
            updated = service.update(db, todo_id, TodoUpdate(status=Status.done))
            if updated:
                return _twiml_response(f"Done: #{todo_id} {updated.title}")
            return _twiml_response(f"Todo #{todo_id} not found.")

        # R: <title> [day]
        reminder_match = re.match(r"^[Rr]:\s*(.+)$", text, re.DOTALL)
        if reminder_match:
            raw_title = reminder_match.group(1).strip()
            title, due_date = _parse_due_date(raw_title)
            todo = service.create(db, TodoCreate(title=title, due_date=due_date, priority=Priority.high))
            reply = f"Saved: #{todo.id} {todo.title}"
            if due_date:
                reply += f"\nDue: {due_date.strftime('%A, %b %d')}"
            return _twiml_response(reply)

        # Unknown
        return _twiml_response(f"Unknown command. Text HELP for options.")

    finally:
        db.close()
