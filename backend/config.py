# backend/config.py
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    anthropic_api_key: str
    voyage_api_key: str
    data_dir: Path = Path(__file__).parent.parent / "data"
    fastapi_port: int = 8000

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env.local"),
        "extra": "ignore",
    }


settings = Settings()
