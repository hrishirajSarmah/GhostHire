from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

API_DR = Path(__file__).parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DR / ".env", extra="ignore")

    database_url: str = "sqlite:///./ghosthire.db"
    anthropic_api_key: str
    embed_backend: Literal["openai", "local"] = "local"
    chroma_db_path: str = str(API_DR / "chroma_db")

settings = Settings()