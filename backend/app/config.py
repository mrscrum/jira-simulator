from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jira_base_url: str
    jira_email: str
    jira_api_token: str
    openai_api_key: str
    database_url: str = "sqlite:///./data/simulator.db"
    environment: str = "production"
    log_level: str = "INFO"
    tick_interval_minutes: int = 30

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
