import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.models.todo import TodoORM, Priority, Status, Category
from src.models.schemas import TodoCreate, TodoUpdate


class TodoService:
    def create(self, db: Session, data: TodoCreate) -> TodoORM:
        todo = TodoORM(
            title=data.title,
            description=data.description,
            due_date=data.due_date,
            priority=data.priority,
            status=data.status,
            tags=json.dumps(data.tags),
            category=data.category,
        )
        db.add(todo)
        db.commit()
        db.refresh(todo)
        return todo

    def get(self, db: Session, todo_id: int) -> Optional[TodoORM]:
        return db.get(TodoORM, todo_id)

    def list_all(
        self,
        db: Session,
        status: Optional[Status] = None,
        priority: Optional[Priority] = None,
        category: Optional[Category] = None,
    ) -> list[TodoORM]:
        q = db.query(TodoORM)
        if status:
            q = q.filter(TodoORM.status == status)
        if priority:
            q = q.filter(TodoORM.priority == priority)
        if category:
            q = q.filter(TodoORM.category == category)
        return q.order_by(TodoORM.created_at.desc()).all()

    def update(self, db: Session, todo_id: int, data: TodoUpdate) -> Optional[TodoORM]:
        todo = db.get(TodoORM, todo_id)
        if not todo:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data:
            update_data["tags"] = json.dumps(update_data["tags"])
        for key, value in update_data.items():
            setattr(todo, key, value)
        todo.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(todo)
        return todo

    def delete(self, db: Session, todo_id: int) -> bool:
        todo = db.get(TodoORM, todo_id)
        if not todo:
            return False
        db.delete(todo)
        db.commit()
        return True

    def get_overdue(self, db: Session) -> list[TodoORM]:
        now = datetime.utcnow()
        return (
            db.query(TodoORM)
            .filter(
                TodoORM.status != Status.done,
                TodoORM.due_date < now,
                (TodoORM.snoozed_until == None) | (TodoORM.snoozed_until < now),  # noqa: E711
            )
            .all()
        )

    def get_stale(self, db: Session, stale_days: int = 3) -> list[TodoORM]:
        now = datetime.utcnow()
        cutoff = now - timedelta(days=stale_days)
        return (
            db.query(TodoORM)
            .filter(
                TodoORM.status != Status.done,
                TodoORM.updated_at < cutoff,
                (TodoORM.last_reminded_at == None) | (TodoORM.last_reminded_at < cutoff),  # noqa: E711
                (TodoORM.snoozed_until == None) | (TodoORM.snoozed_until < now),  # noqa: E711
            )
            .all()
        )

    def get_overdue_or_stale(self, db: Session) -> list[TodoORM]:
        """Kept for backwards compatibility — returns overdue + stale combined."""
        seen = {t.id for t in self.get_overdue(db)}
        result = list(self.get_overdue(db))
        for t in self.get_stale(db):
            if t.id not in seen:
                result.append(t)
        return result

    def mark_reminded(self, db: Session, todo_id: int) -> None:
        todo = db.get(TodoORM, todo_id)
        if todo:
            todo.last_reminded_at = datetime.utcnow()
            db.commit()
