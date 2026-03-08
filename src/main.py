from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.config import settings
from src.database import Base, engine
from src.services.reminder_service import start_scheduler
from src.services.imessage_service import initialize_last_rowid, check_inbound_messages
from src.api import reminders, todos, agent, upload, sms
from src.mcp_server import mcp


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler = start_scheduler(settings.reminder_check_interval_minutes)
    initialize_last_rowid()
    scheduler.add_job(
        check_inbound_messages,
        trigger="interval",
        minutes=settings.imessage_poll_interval_minutes,
        id="imessage_poll",
        replace_existing=True,
    )
    yield
    scheduler.shutdown()


app = FastAPI(
    title="organizer-api",
    version="1.0.0",
    description="AI-powered todo management agent",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "details": None,
            },
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# Order matters: reminders must come before todos to avoid /todos/reminders
# being matched as /todos/{todo_id} with todo_id="reminders"
app.include_router(reminders.router, prefix="/api/v1")
app.include_router(todos.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(sms.router, prefix="/api/v1")


app.mount("/mcp", mcp.sse_app())


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
