import json

import anthropic
from sqlalchemy.orm import Session

from src.config import settings
from src.models.todo import Status
from src.services.todo_service import TodoService


class CategoryService:
    def __init__(self):
        self.client = (
            anthropic.Anthropic(api_key=settings.anthropic_api_key)
            if settings.anthropic_api_key
            else None
        )
        self.todo_service = TodoService()

    def analyze(self, db: Session) -> list[dict]:
        todos = self.todo_service.list_all(db)
        open_todos = [t for t in todos if t.status != Status.done]

        if not open_todos:
            return []

        grouped: dict = {}
        for t in open_todos:
            key = t.category.value if t.category else "uncategorized"
            grouped.setdefault(key, []).append(t)

        results = []
        for category_name, items in sorted(grouped.items()):
            task_list = [
                {
                    "id": t.id,
                    "title": t.title,
                    "priority": t.priority,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                }
                for t in items
            ]

            if self.client:
                analysis = self._analyze_category(category_name, task_list)
            else:
                analysis = {
                    "commonalities": "AI unavailable.",
                    "strategy": "No API key configured.",
                }

            results.append(
                {
                    "category": category_name,
                    "tasks": task_list,
                    "commonalities": analysis["commonalities"],
                    "strategy": analysis["strategy"],
                }
            )

        return results

    def _analyze_category(self, category: str, tasks: list[dict]) -> dict:
        if len(tasks) == 1:
            return {
                "commonalities": "Single task in this category.",
                "strategy": f"Focus on: {tasks[0]['title']}",
            }

        prompt = (
            f"You are analyzing a group of tasks in the '{category}' category.\n\n"
            f"Tasks:\n{json.dumps(tasks, indent=2)}\n\n"
            "Respond with a JSON object with exactly two keys:\n"
            '- "commonalities": one sentence identifying shared themes, dependencies, or blockers\n'
            '- "strategy": one to two sentences suggesting a concrete approach for tackling this group together\n\n'
            "Respond ONLY with valid JSON, no extra text."
        )

        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

        return json.loads(response.content[0].text)
