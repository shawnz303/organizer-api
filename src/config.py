from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str | None = None
    anthropic_auth_token: str | None = None
    database_url: str = "sqlite:///./todos.db"
    port: int = 8000
    reminder_check_interval_minutes: int = 60
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    user_phone_number: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()
