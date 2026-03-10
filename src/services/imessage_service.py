import json
import logging
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import anthropic
from apscheduler.schedulers.background import BackgroundScheduler

from src.config import settings
from src.database import SessionLocal
from src.models.schemas import TodoCreate, TodoUpdate
from src.models.todo import Status
from src.services.agent_service import AgentService
from src.services.category_service import CategoryService
from src.services.todo_service import TodoService

logger = logging.getLogger(__name__)

IMESSAGE_DB = Path.home() / "Library/Messages/chat.db"
PT = ZoneInfo("America/Los_Angeles")

_last_seen_rowid: int = 0

# Rolling conversation history — last 10 messages (5 exchanges)
_conversation_history: list[dict] = []
_last_message_time: Optional[datetime] = None
_HISTORY_MAX = 10
_HISTORY_TTL_HOURS = 2


def _get_time_context() -> str:
    now = datetime.now(PT)
    return f"Today is {now.strftime('%A, %B %d %Y')}, {now.strftime('%I:%M %p')} PT."


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


def notify(message: str) -> None:
    """Send an iMessage to the configured user handle."""
    if settings.user_imessage_handle:
        _send_imessage(settings.user_imessage_handle, message)


def _get_todo_list_text(priority_only: bool = False, week_only: bool = False) -> str:
    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
        if not todos:
            return "No todos."

        open_todos = [t for t in todos if t.status != Status.done]

        if priority_only:
            open_todos = [t for t in open_todos if t.priority == "high"]
            if not open_todos:
                return "No high-priority todos."

        if week_only:
            now = datetime.now(PT)
            week_end = now + timedelta(days=(6 - now.weekday()))
            open_todos = [
                t for t in open_todos
                if t.due_date and t.due_date.replace(tzinfo=PT if t.due_date.tzinfo is None else None) <= week_end.replace(tzinfo=None)
            ]
            if not open_todos:
                return "Nothing due this week."

        grouped: dict = {}
        for t in open_todos:
            key = t.category.value if t.category else "uncategorized"
            grouped.setdefault(key, []).append(t)

        lines = []
        for category, items in sorted(grouped.items()):
            lines.append(f"— {category.upper()} —")
            for t in items:
                due = f" (due {t.due_date.strftime('%m/%d')})" if t.due_date else ""
                snooze = " [snoozed]" if t.snoozed_until and t.snoozed_until > datetime.utcnow() else ""
                lines.append(f"[{t.id}] {t.title}{due} [{t.priority}]{snooze}")
            lines.append("")
        return "\n".join(lines).strip()
    finally:
        db.close()


def _get_category_analysis_text() -> str:
    db = SessionLocal()
    try:
        results = CategoryService().analyze(db)
    finally:
        db.close()

    if not results:
        return "No open todos."

    lines = []
    for item in results:
        lines.append(f"— {item['category'].upper()} —")
        for t in item["tasks"]:
            due = f" (due {t['due_date'][:10]})" if t["due_date"] else ""
            lines.append(f"• {t['title']}{due} [{t['priority']}]")
        lines.append(f"Themes: {item['commonalities']}")
        lines.append(f"Strategy: {item['strategy']}")
        lines.append("")
    return "\n".join(lines).strip()


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


def _parse_snooze_duration(token: str) -> Optional[datetime]:
    """Parse snooze tokens like '2h', '4h', 'tomorrow', 'monday'."""
    token = token.strip().lower()
    now = datetime.now(PT).replace(tzinfo=None)
    match = re.match(r"^(\d+)h$", token)
    if match:
        return now + timedelta(hours=int(match.group(1)))
    if token == "tomorrow":
        return (now + timedelta(days=1)).replace(hour=8, minute=0, second=0)
    days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}
    if token in days:
        target_dow = days[token]
        current_dow = now.weekday()
        delta = (target_dow - current_dow) % 7 or 7
        return (now + timedelta(days=delta)).replace(hour=8, minute=0, second=0)
    return None


def _expand_todo_description(title: str) -> Optional[str]:
    if not settings.anthropic_api_key:
        return None
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": (
            f"Turn this task headline into a detailed, actionable plan:\n\n\"{title}\"\n\n"
            "Include: goal, key steps, dependencies or blockers to consider, and a definition of done. "
            "Be concise but thorough. Plain text only, no markdown."
        )}],
    )
    return response.content[0].text.strip()


def _create_todo_from_text(text: str, due_date: Optional[datetime] = None, category=None) -> str:
    title = text.strip()
    if not title:
        return "No title provided."
    description = _expand_todo_description(title)
    db = SessionLocal()
    try:
        service = TodoService()
        todo = service.create(db, TodoCreate(title=title, due_date=due_date, category=category, description=description))
        due_str = f" due {due_date.strftime('%m/%d')}" if due_date else ""
        cat_str = f" [{todo.category.value}]" if todo.category else ""
        return f"Created: {todo.title}{due_str}{cat_str}"
    finally:
        db.close()


def _create_reminder_from_text(text: str) -> str:
    from src.models.todo import Category
    parts = text.strip().split()
    if not parts:
        return "No reminder text provided."

    due_date = None
    category = None

    if len(parts) >= 2:
        candidate = parts[-1]
        due_date = _parse_date(candidate)
        if due_date:
            parts = parts[:-1]

    if len(parts) >= 2:
        candidate = parts[-1].lower()
        try:
            category = Category(candidate)
            parts = parts[:-1]
        except ValueError:
            pass

    title = " ".join(parts)
    return _create_todo_from_text(title, due_date, category)


def _get_focus_block_suggestion() -> str:
    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
    finally:
        db.close()

    open_todos = [t for t in todos if t.status != Status.done]
    if not open_todos:
        return "Nothing on your list. Take a break!"

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
    if not client:
        return "AI unavailable."

    todo_summaries = [
        {
            "id": t.id,
            "title": t.title,
            "category": t.category.value if t.category else None,
            "due_date": t.due_date.strftime("%m/%d") if t.due_date else None,
            "priority": t.priority,
        }
        for t in open_todos
    ]

    prompt = (
        f"{_get_time_context()}\n\n"
        f"Here are the user's open todos:\n{json.dumps(todo_summaries, indent=2)}\n\n"
        "Recommend a focus block: pick the single best category to work on right now and "
        "identify the 2-3 tasks within it to tackle. Explain why this category/set makes sense "
        "given the time of day and urgency. Be direct, plain text, no markdown, 4-6 lines max."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _get_next_task_recommendation() -> str:
    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
    finally:
        db.close()

    open_todos = [t for t in todos if t.status != Status.done]
    if not open_todos:
        return "Nothing on your list. Take a break!"

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
    if not client:
        return "AI unavailable — no API key configured."

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
        f"{_get_time_context()}\n\n"
        f"Here are the user's open todos:\n{json.dumps(todo_summaries, indent=2)}\n\n"
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


def _send_morning_summary() -> None:
    if not settings.user_imessage_handle:
        return

    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
    finally:
        db.close()

    if not todos:
        notify("No todos for today. Clean slate!")
        return

    open_todos = [t for t in todos if t.status != Status.done]
    todo_summaries = [
        {
            "id": t.id,
            "title": t.title,
            "due_date": t.due_date.strftime("%m/%d") if t.due_date else None,
            "priority": t.priority,
            "category": t.category.value if t.category else None,
        }
        for t in open_todos
    ]

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
    if not client:
        return

    prompt = (
        f"{_get_time_context()}\n\n"
        f"Here are the user's open todos:\n{json.dumps(todo_summaries, indent=2)}\n\n"
        "Write a short, friendly morning iMessage giving them their top 3-5 priorities for today. "
        "Lead with any overdue or due-today items. Be concise — bullet points, plain text, no markdown, no sign-off."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    notify(f"Good morning!\n\n{response.content[0].text.strip()}")
    logger.info("Morning summary sent")


def _send_midday_checkin() -> None:
    if not settings.user_imessage_handle:
        return

    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
    finally:
        db.close()

    open_todos = [t for t in todos if t.status != Status.done]
    if not open_todos:
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
    if not client:
        return

    todo_summaries = [
        {
            "id": t.id,
            "title": t.title,
            "due_date": t.due_date.strftime("%m/%d") if t.due_date else None,
            "priority": t.priority,
            "category": t.category.value if t.category else None,
        }
        for t in open_todos
    ]

    prompt = (
        f"{_get_time_context()}\n\n"
        f"Open todos:\n{json.dumps(todo_summaries, indent=2)}\n\n"
        "It's early afternoon. Give a quick mid-day check-in: what 1-2 things should the user "
        "focus on for the rest of today? Consider what's overdue and what can realistically get done. "
        "2-3 lines max. Plain text, no markdown."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    notify(f"Afternoon check-in:\n\n{response.content[0].text.strip()}")
    logger.info("Midday check-in sent")


def _send_eod_friday_wrapup() -> None:
    if not settings.user_imessage_handle:
        return

    db = SessionLocal()
    try:
        service = TodoService()
        todos = service.list_all(db)
    finally:
        db.close()

    open_todos = [t for t in todos if t.status != Status.done]
    if not open_todos:
        notify("Heading into the weekend with a clean slate.")
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
    if not client:
        return

    todo_summaries = [
        {
            "id": t.id,
            "title": t.title,
            "due_date": t.due_date.strftime("%m/%d") if t.due_date else None,
            "priority": t.priority,
            "category": t.category.value if t.category else None,
        }
        for t in open_todos
    ]

    prompt = (
        f"{_get_time_context()}\n\n"
        f"Open todos:\n{json.dumps(todo_summaries, indent=2)}\n\n"
        "It's end of week. Give a brief EOD Friday message: what 1-2 things could they still "
        "close out today, and what's the top priority to hit first thing Monday? "
        "3-4 lines max. Plain text, no markdown, no fluff."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    notify(f"End of week:\n\n{response.content[0].text.strip()}")
    logger.info("EOD Friday wrap-up sent")


def _update_conversation_history(role: str, content: str) -> None:
    global _conversation_history, _last_message_time
    now = datetime.utcnow()

    # Reset history if idle for too long
    if _last_message_time and (now - _last_message_time).total_seconds() > _HISTORY_TTL_HOURS * 3600:
        _conversation_history = []

    _conversation_history.append({"role": role, "content": content})
    if len(_conversation_history) > _HISTORY_MAX:
        _conversation_history = _conversation_history[-_HISTORY_MAX:]
    _last_message_time = now


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
        if not text or (not text.startswith("/") and not text.startswith(".")):
            continue

        cmd = text.strip()
        reply = None

        if cmd == "/s":
            reply = _get_todo_list_text()
            logger.info("iMessage /s → sending todo list")

        elif cmd == "/p":
            reply = _get_todo_list_text(priority_only=True)
            logger.info("iMessage /p → sending high-priority list")

        elif cmd == "/w":
            reply = _get_todo_list_text(week_only=True)
            logger.info("iMessage /w → sending week view")

        elif cmd == "/q":
            reply = _get_next_task_recommendation()
            logger.info("iMessage /q → sending task recommendation")

        elif cmd == "/c":
            reply = _get_category_analysis_text()
            logger.info("iMessage /c → sending category analysis")

        elif cmd == "/focus":
            reply = _get_focus_block_suggestion()
            logger.info("iMessage /focus → sending focus block suggestion")

        elif cmd.startswith("/done "):
            parts = cmd[6:].strip().split()
            if parts and parts[0].isdigit():
                todo_id = int(parts[0])
                db = SessionLocal()
                try:
                    service = TodoService()
                    updated = service.update(db, todo_id, TodoUpdate(status=Status.done))
                    reply = f"Done: {updated.title}" if updated else f"Todo {todo_id} not found."
                finally:
                    db.close()
            else:
                reply = "Usage: /done <ID>"
            logger.info(f"iMessage /done → {reply}")

        elif cmd.startswith("/snooze "):
            parts = cmd[8:].strip().split()
            if len(parts) >= 2 and parts[0].isdigit():
                todo_id = int(parts[0])
                snooze_until = _parse_snooze_duration(parts[1])
                if snooze_until:
                    db = SessionLocal()
                    try:
                        service = TodoService()
                        updated = service.update(db, todo_id, TodoUpdate(snoozed_until=snooze_until))
                        until_str = snooze_until.strftime("%a %m/%d %I:%M %p")
                        reply = f"Snoozed '{updated.title}' until {until_str}." if updated else f"Todo {todo_id} not found."
                    finally:
                        db.close()
                else:
                    reply = "Usage: /snooze <ID> <2h|tomorrow|monday|...>"
            else:
                reply = "Usage: /snooze <ID> <2h|tomorrow|monday|...>"
            logger.info(f"iMessage /snooze → {reply}")

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

        elif cmd.startswith("/"):
            reply = "Commands: /s /p /w /q /c /focus /r /done /snooze"

        if reply and settings.user_imessage_handle:
            _send_imessage(settings.user_imessage_handle, reply)

        elif text.startswith("."):
            nl_cmd = text.strip()[1:].strip()
            _update_conversation_history("user", nl_cmd)
            db = SessionLocal()
            try:
                agent = AgentService()
                # Pass conversation history (excluding the message we just added)
                history = _conversation_history[:-1] if len(_conversation_history) > 1 else []
                result = agent.chat(db, nl_cmd, history=history)
                reply = result["reply"]
            finally:
                db.close()
            if reply:
                _update_conversation_history("assistant", reply)
                if settings.user_imessage_handle:
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
        _send_morning_summary,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8,
        minute=0,
        timezone="America/Los_Angeles",
        id="morning_summary",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_midday_checkin,
        trigger="cron",
        day_of_week="mon-fri",
        hour=13,
        minute=0,
        timezone="America/Los_Angeles",
        id="midday_checkin",
        replace_existing=True,
    )
    scheduler.add_job(
        _send_eod_friday_wrapup,
        trigger="cron",
        day_of_week="fri",
        hour=16,
        minute=0,
        timezone="America/Los_Angeles",
        id="eod_friday",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"iMessage poller started (every {settings.imessage_poll_interval_seconds}s)")
    logger.info("Scheduled: morning 8 AM PT Mon-Fri, midday 1 PM PT Mon-Fri, EOD 4 PM PT Fri")
    return scheduler
