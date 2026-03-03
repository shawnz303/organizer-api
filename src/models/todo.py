import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Enum, DateTime, Text, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Status(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


class Category(str, enum.Enum):
    sales = "sales"
    engineering = "engineering"
    product = "product"
    fundraising = "fundraising"
    ops = "ops"


class TodoORM(Base):
    __tablename__ = "todos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    priority: Mapped[Priority] = mapped_column(Enum(Priority), default=Priority.medium)
    status: Mapped[Status] = mapped_column(Enum(Status), default=Status.pending)
    tags: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_reminded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    category: Mapped[Optional[Category]] = mapped_column(Enum(Category), nullable=True)
