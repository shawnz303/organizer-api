"""Seed the organizer with tasks from the CIED consulting engagement SOW."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import Base, engine, SessionLocal
from src.models.schemas import TodoCreate
from src.models.todo import Priority, Status
from src.services.todo_service import TodoService

Base.metadata.create_all(bind=engine)

TODOS = [
    # Immediate action
    TodoCreate(
        title="Call Molly Haggerty",
        description="Call Molly Haggerty at +1 (408) 348-5791. Scheduled Feb 26, 4:00–4:30pm.",
        priority=Priority.high,
        status=Status.pending,
        tags=["call", "cied", "engagement"],
    ),
    # CIED Leadership Change Management
    TodoCreate(
        title="Coach two new CIED managers",
        description="Provide coaching and support to the two new CIED managers through leadership transition.",
        priority=Priority.high,
        status=Status.pending,
        tags=["cied", "coaching", "leadership"],
    ),
    TodoCreate(
        title="Organize CIED team structure",
        description="Assess and establish correct organization and structure for the CIED team.",
        priority=Priority.high,
        status=Status.pending,
        tags=["cied", "org-design", "leadership"],
    ),
    # Onboarding & Offboarding
    TodoCreate(
        title="Review current onboarding and offboarding processes",
        description="Audit existing onboarding and offboarding workflows and identify gaps.",
        priority=Priority.medium,
        status=Status.pending,
        tags=["onboarding", "offboarding", "process"],
    ),
    TodoCreate(
        title="Provide recommendations for onboarding/offboarding improvement",
        description="Document and present improvement recommendations based on process review.",
        priority=Priority.medium,
        status=Status.pending,
        tags=["onboarding", "offboarding", "recommendations"],
    ),
    TodoCreate(
        title="Implement onboarding/offboarding improvements",
        description="Execute approved changes to onboarding and offboarding processes.",
        priority=Priority.medium,
        status=Status.pending,
        tags=["onboarding", "offboarding", "implementation"],
    ),
    TodoCreate(
        title="Own onboarding/offboarding for SOW engagement duration",
        description="Manage and own end-to-end onboarding/offboarding (~1-2 people/month) for 3-month engagement.",
        priority=Priority.medium,
        status=Status.in_progress,
        tags=["onboarding", "offboarding", "ongoing"],
    ),
    # Insperity
    TodoCreate(
        title="Insperity management — interface with Briana",
        description="Coordinate and manage Insperity relationship, point of contact is Briana.",
        priority=Priority.medium,
        status=Status.pending,
        tags=["insperity", "hr", "operations"],
    ),
    # Recruitment
    TodoCreate(
        title="Set up full cycle recruitment — Engineering",
        description="Build out full cycle recruiting process for Engineering roles.",
        priority=Priority.medium,
        status=Status.pending,
        tags=["recruitment", "engineering", "hiring"],
    ),
    TodoCreate(
        title="Set up full cycle recruitment — CIED",
        description="Build out full cycle recruiting process for CIED roles.",
        priority=Priority.medium,
        status=Status.pending,
        tags=["recruitment", "cied", "hiring"],
    ),
    # Finance (from reminder)
    TodoCreate(
        title="Pay Claudio and set up Ramp rules",
        description="Process payment to Claudio and configure Ramp expense rules to route to Shawn.",
        priority=Priority.high,
        status=Status.pending,
        tags=["finance", "ramp", "payments"],
    ),
]


def run():
    db = SessionLocal()
    service = TodoService()
    created = 0
    try:
        for todo_data in TODOS:
            service.create(db, todo_data)
            created += 1
            print(f"  + {todo_data.title}")
    finally:
        db.close()
    print(f"\nSeeded {created} todos.")


if __name__ == "__main__":
    print("Seeding engagement todos...\n")
    run()
