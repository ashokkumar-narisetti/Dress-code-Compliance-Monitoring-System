"""
database.py - SQLAlchemy database connection setup.
Reads DATABASE_URL from .env and creates the engine, session factory, and Base class.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic_settings import BaseSettings

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_DEFAULT_MODEL = _PROJECT_ROOT / "dresscode.pt"
_FALLBACK_MODEL = _BACKEND_DIR / "models" / "best.pt"


def _default_model_path() -> str:
    if _DEFAULT_MODEL.is_file():
        return str(_DEFAULT_MODEL)
    if _FALLBACK_MODEL.is_file():
        return str(_FALLBACK_MODEL)
    return str(_FALLBACK_MODEL)


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/dresscode_db"
    SECRET_KEY: str = "your-super-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    UPLOAD_DIR: str = "uploads"
    VIDEO_DIR: str = "uploads/videos"
    EVIDENCE_DIR: str = "uploads/evidence"
    MODEL_PATH: str = _default_model_path()
    FRAMES_INTERVAL: int = 20
    TEMP_FRAMES_DIR: str = "uploads/temp_frames"

    class Config:
        env_file = ".env"


settings = Settings()

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency to yield a DB session and close it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
