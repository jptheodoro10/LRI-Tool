from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / '.env', BACKEND_DIR / '.env'),
        extra='ignore',
    )

    app_name: str = 'LRI Tool API'
    auth_mode: str = 'local'
    ai_mode: str = 'mock'

    database_url: str = 'postgresql://lri:lri@db:5432/lri'
    jwt_secret: str = 'change-me'
    jwt_expires_minutes: int = 240

    invite_expiration_days: int = 7
    ai_poll_interval_seconds: int = 2
    ai_job_timeout_seconds: int = 30

    llm_provider: str = 'openai'
    llm_api_key: str = Field(
        default='',
        validation_alias=AliasChoices('OPENAI_API_KEY', 'LLM_API_KEY'),
    )
    llm_model: str = 'gpt-4o-mini'
    llm_timeout_seconds: int = 20


settings = Settings()
