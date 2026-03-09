import json
import logging
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import anthropic
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings
from src.database import SessionLocal
from src.models.schemas import TodoCreate
from src.services.todo_service import TodoService

logger = logging.getLogger(__name__)

IMESSAGE_DB = Path.home() / "Library/Messages/chat.db"

_last_seen_rowid: int = 0


def _extract_text(text: Optional[str], attributed_body: Optional[bytes]) -> Optional[str]:
    if text:
        return text
    if not attributed_body:
        return None
    b = bytes(attributed_body)
    marker = b"NSString\x01"
    idx = b.find(marker)
    if idx == -1:
        return None
    plus_pos = b.find(b"+", idx + len(marker), idx + len(marker) + 20)
    if plus_pos == -1:
        return None
    length = b[plus_pos + 1]
    return b[plus_pos + 2 : plus_pos + 2 + length].decode("utf-8", errors="replace")


def _send_imessage(handle: str, text: str) -> None:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''tell application "Messages"
    set s to 1st service whose service type = iMessage
    set b to buddy "{handle}" of s
    send "{escaped}" to b
end tell'''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"iMessage send failed: {result.stderr.strip()}")


def _get_todo_list_text() -> str:
    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
        if not todos:
            return "No todos."
        lines = []
        for t in todos:
            due = f" (due {t.due_date.strftime('%m/%d')})" if t.due_date else ""
            lines.append(f"[{t.status}] {t.title}{due} [{t.priority}]")
        return "\n".join(lines)
    finally:
        db.close()


def _parse_date(token: str) -> Optional[datetime]:
    token = token.strip().lower()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if token == "today":
        return today
    if token == "tomorrow":
        return today + timedelta(days=1)
    match = re.match(r"^(\d{1,2})/(\d{1,2})$", token)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        year = today.year
        try:
            dt = today.replace(year=year, month=month, day=day)
            if dt < today:
                dt = dt.replace(year=year + 1)
            return dt
        except ValueError:
            pass
    return None


def _create_todo_from_text(text: str, due_date: Optional[datetime] = None) -> str:
    title = text.strip()
    if not title:
        return "No title provided."
    db = SessionLocal()
    try:
        service = TodoService()
        todo = service.create(db, TodoCreate(title=title, due_date=due_date))
        due_str = f" due {due_date.strftime('%m/%d')}" if due_date else ""
        return f"Created: {todo.title}{due_str}"
    finally:
        db.close()


def _create_reminder_from_text(text: str) -> str:
    parts = text.strip().split()
    if not parts:
        return "No reminder text provided."
    due_date = None
    if len(parts) >= 2:
        candidate = parts[-1]
        due_date = _parse_date(candidate)
        if due_date:
            parts = parts[:-1]
    title = " ".join(parts)
    return _create_todo_from_text(title, due_date)


def _send_nightly_summary() -> None:
    if not settings.user_imessage_handle:
        logger.warning("Nightly summary skipped: user_imessage_handle not set")
        return

    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
    finally:
        db.close()

    if not todos:
        _send_imessage(settings.user_imessage_handle, "No todos for tomorrow. Clean slate!")
        return

    tomorrow = datetime.now().date()
    todo_summaries = [
        {
            "id": t.id,
            "title": t.title,
            "due_date": t.due_date.strftime("%m/%d") if t.due_date else None,
            "priority": t.priority,
            "status": t.status,
        }
        for t in todos
        if t.status != "done"
    ]

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
    if not client:
        logger.warning("Nightly summary skipped: no Anthropic API key")
        return

    prompt = (
        f"Today is {tomorrow}. Here are the user's open todos:\n\n"
        f"{json.dumps(todo_summaries, indent=2)}\n\n"
        "Write a short, friendly iMessage-style summary of their top priorities for today. "
        "Be concise — 3-5 bullet points max. Lead with the most urgent/important items. "
        "No fluff, no sign-off. Use plain text, no markdown."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    summary = response.content[0].text.strip()
    _send_imessage(settings.user_imessage_handle, f"Good morning! Today's priorities:\n\n{summary}")
    logger.info("Nightly summary sent")


def _get_next_task_recommendation() -> str:
    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
    finally:
        db.close()

    open_todos = [t for t in todos if t.status != "done"]
    if not open_todos:
        return "Nothing on your list. Take a break!"

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
    if not client:
        return "AI unavailable — no API key configured."

    today = datetime.now().date()
    todo_summaries = [
        {
            "id": t.id,
            "title": t.title,
            "due_date": t.due_date.strftime("%m/%d") if t.due_date else None,
            "priority": t.priority,
            "status": t.status,
        }
        for t in open_todos
    ]

    prompt = (
        f"Today is {today}. Here are the user's open todos:\n\n"
        f"{json.dumps(todo_summaries, indent=2)}\n\n"
        "The user just asked: 'What should I work on right now?' "
        "Pick the single most important task and explain in 1-2 sentences why it's the top priority. "
        "Be direct and actionable. No fluff. Plain text only."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def poll_imessage() -> None:
    global _last_seen_rowid
    if not IMESSAGE_DB.exists():
        return

    try:
        conn = sqlite3.connect(f"file:{IMESSAGE_DB}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rowid, text, attributedBody FROM message WHERE is_from_me = 1 AND rowid > ? ORDER BY rowid ASC",
            (_last_seen_rowid,),
        )
        rows = cursor.fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"iMessage DB read error: {e}")
        return

    for rowid, raw_text, attributed_body in rows:
        _last_seen_rowid = rowid
        text = _extract_text(raw_text, attributed_body)
        if not text or not text.startswith("/"):
            continue

        cmd = text.strip()
        reply = None

        if cmd == "/s":
            reply = _get_todo_list_text()
            logger.info("iMessage /s → sending todo list")

        elif cmd == "/q":
            reply = _get_next_task_recommendation()
            logger.info("iMessage /q → sending task recommendation")

        elif cmd.startswith("/r "):
            content = cmd[3:].strip()
            confirmation = _create_reminder_from_text(content)
            logger.info(f"iMessage /r → {confirmation}")
            if settings.user_imessage_handle:
                _send_imessage(settings.user_imessage_handle, confirmation)
                _send_imessage(settings.user_imessage_handle, _get_todo_list_text())
            continue

        elif cmd.startswith("/r"):
            reply = "Usage: /r <title> [today|tomorrow|MM/DD]"

        if reply and settings.user_imessage_handle:
            _send_imessage(settings.user_imessage_handle, reply)


def _init_last_seen_rowid() -> None:
    global _last_seen_rowid
    if not IMESSAGE_DB.exists():
        return
    try:
        conn = sqlite3.connect(f"file:{IMESSAGE_DB}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(MAX(rowid), 0) FROM message WHERE is_from_me = 1")
        row = cursor.fetchone()
        conn.close()
        if row and row[0]:
            _last_seen_rowid = row[0]
    except Exception as e:
        logger.error(f"iMessage init error: {e}")


def start_imessage_poller() -> BackgroundScheduler:
    _init_last_seen_rowid()
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        poll_imessage,
        trigger="interval",
        seconds=settings.imessage_poll_interval_seconds,
        id="imessage_poll",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_nightly_summary,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8,
        minute=0,
        timezone="America/Los_Angeles",
        id="nightly_summary",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"iMessage poller started (every {settings.imessage_poll_interval_seconds}s)")
    logger.info("Morning summary scheduled for 8:00 AM PT, Mon-Fri")
    return scheduler
