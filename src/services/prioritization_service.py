import json
from datetime import datetime

import anthropic
from sqlalchemy.orm import Session

from src.config import settings
from src.models.schemas import TodoUpdate
from src.models.todo import TodoORM
from src.services.todo_service import TodoService


class PrioritizationService:
    def __init__(self):
        self.client = (
            anthropic.Anthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )
        self.todo_service = TodoService()

    def prioritize(self, db: Session, todos: list[TodoORM]) -> list[dict]:
        if not self.client:
            return [{"error": "AI features are disabled — no Anthropic API key configured."}]

        if not todos:
            return []

        now = datetime.utcnow()
        todo_summaries = [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "current_priority": t.priority,
                "status": t.status,
                "tags": json.loads(t.tags or "[]"),
                "created_at": t.created_at.isoformat(),
            }
            for t in todos
        ]

        prompt = (
            f"You are a task prioritization expert. Today is {now.isoformat()} UTC.\n\n"
            "Analyze the following todo items and return a JSON array ranked from highest "
            "to lowest priority. For each item, include:\n"
            "- id: the original todo id\n"
            '- suggested_priority: "high", "medium", or "low"\n'
            "- rank: 1-based integer (1 = most urgent)\n"
            "- reasoning: one sentence explaining the ranking\n\n"
            "Consider: due dates (closer = higher priority), urgency keywords in "
            "titles/descriptions, current priority hints, and task staleness.\n\n"
            "Respond ONLY with a valid JSON array, no explanation text outside the JSON.\n\n"
            f"Todos:\n{json.dumps(todo_summaries, indent=2)}"
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text
        ranked = json.loads(raw)

        for item in ranked:
            self.todo_service.update(
                db,
                item["id"],
                TodoUpdate(priority=item["suggested_priority"]),
            )

        return ranked
