from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Verity Reconciliation Engine"
    env: str = "development"
    port: int = 8000
    host: str = "0.0.0.0"
    database_url: str = "sqlite:///./verity.db"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
