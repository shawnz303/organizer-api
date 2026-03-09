from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: Optional[str] = None
    database_url: str = "sqlite:///./todos.db"
    port: int = 8000
    reminder_check_interval_minutes: int = 60
    user_imessage_handle: Optional[str] = None
    imessage_poll_interval_seconds: int = 30

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
