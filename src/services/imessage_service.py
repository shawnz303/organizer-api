import os
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta

from src.config import settings

# ---------------------------------------------------------------------------
# Outbound
# ---------------------------------------------------------------------------

def send_imessage(body: str, to: str | None = None) -> bool:
    """Send a message via Messages.app using osascript. Returns True on success."""
    handle = to or settings.user_imessage_handle
    if not handle:
        return False
    escaped = body.replace("\\", "\\\\").replace('"', '\\"')
    script = (
        f'tell application "Messages" to send "{escaped}" '
        f'to buddy "{handle}" of service "iMessage"'
    )
    result = subprocess.run(["osascript", "-"], input=script.encode(), capture_output=True)
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Inbound polling
# ---------------------------------------------------------------------------

_last_rowid: int = 0


def initialize_last_rowid() -> None:
    """Call once at startup so old messages are not replayed after a restart."""
    global _last_rowid
    handle = settings.user_imessage_handle
    if not handle:
        return
    db_path = os.path.expanduser(settings.messages_db_path)
    if not os.path.exists(db_path):
        return
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = con.execute(
                "SELECT COALESCE(MAX(m.ROWID), 0) FROM message m "
                "JOIN handle h ON h.ROWID = m.handle_id WHERE h.id = ?",
                (handle,),
            ).fetchone()
            _last_rowid = row[0] if row else 0
        finally:
            con.close()
    except Exception:
        pass


def poll_inbound_messages() -> list[dict]:
    """Return new inbound messages from the configured handle since the last poll."""
    global _last_rowid
    handle = settings.user_imessage_handle
    if not handle:
        return []
    db_path = os.path.expanduser(settings.messages_db_path)
    if not os.path.exists(db_path):
        return []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT m.ROWID, m.text FROM message m "
                "JOIN handle h ON h.ROWID = m.handle_id "
                "WHERE h.id = ? AND m.ROWID > ? AND m.is_from_me = 0 "
                "ORDER BY m.ROWID ASC",
                (handle, _last_rowid),
            ).fetchall()
            if rows:
                _last_rowid = rows[-1][0]
            return [{"rowid": r[0], "text": r[1]} for r in rows if r[1]]
        finally:
            con.close()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Command parsing (shared with Twilio webhook in src/api/sms.py)
# ---------------------------------------------------------------------------

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


def parse_due_date(text: str) -> tuple[str, datetime | None]:
    """Extract a trailing day name and return (cleaned_title, due_date)."""
    words = text.strip().split()
    if words:
        last = words[-1].lower().rstrip(".,")
        if last in _DAY_NAMES:
            today = datetime.utcnow()
            target_weekday = _DAY_NAMES[last]
            days_ahead = (target_weekday - today.weekday()) % 7 or 7
            due = (today + timedelta(days=days_ahead)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            title = " ".join(words[:-1]).strip() or text.strip()
            return title, due
    return text.strip(), None


def process_command(text: str) -> str:
    """Parse a text command and return a plain-string reply."""
    from src.database import SessionLocal
    from src.models.schemas import TodoCreate, TodoUpdate
    from src.models.todo import Priority, Status
    from src.services.todo_service import TodoService

    upper = text.strip().upper()
    db = SessionLocal()
    service = TodoService()
    try:
        if upper in ("HELP", "H", "?"):
            return HELP_TEXT

        if upper in ("LIST", "L", "LS"):
            todos = service.list_all(db, status=Status.pending)
            if not todos:
                return "No pending todos."
            lines = [
                f"#{t.id} [{t.priority.value}] {t.title}"
                + (f" (due {t.due_date.strftime('%a %b %d')})" if t.due_date else "")
                for t in todos[:10]
            ]
            return "\n".join(lines)

        done_match = re.match(r"^(?:DONE|D|COMPLETE)\s+(\d+)$", upper)
        if done_match:
            todo_id = int(done_match.group(1))
            updated = service.update(db, todo_id, TodoUpdate(status=Status.done))
            if updated:
                return f"Done: #{todo_id} {updated.title}"
            return f"Todo #{todo_id} not found."

        reminder_match = re.match(r"^[Rr]:\s*(.+)$", text.strip(), re.DOTALL)
        if reminder_match:
            raw_title = reminder_match.group(1).strip()
            title, due_date = parse_due_date(raw_title)
            todo = service.create(db, TodoCreate(title=title, due_date=due_date, priority=Priority.high))
            reply = f"Saved: #{todo.id} {todo.title}"
            if due_date:
                reply += f"\nDue: {due_date.strftime('%A, %b %d')}"
            return reply

        return "Unknown command. Text HELP for options."
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scheduled job
# ---------------------------------------------------------------------------

def check_inbound_messages() -> None:
    """Scheduled job: poll for new iMessages and dispatch commands."""
    for msg in poll_inbound_messages():
        try:
            reply = process_command(msg["text"])
            send_imessage(reply)
        except Exception:
            pass
