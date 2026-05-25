# backend/config.py
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    anthropic_api_key: str
    data_dir: Path = Path(__file__).parent.parent / "data"
    fastapi_port: int = 8000
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env.local"),
        "extra": "ignore",
    }


settings = Settings()
