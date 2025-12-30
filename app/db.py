# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pgvector.sqlalchemy import Vector
from app.config import get_settings


settings = get_settings()

# Synchronous engine is enough for now
engine = create_engine(
    settings.database_url,
    echo=False,  # set True if you want to see SQL queries
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    """
    Base class for ORM models.
    """
    pass


# Re-export Vector so models.py can import from app.db
VectorType = Vector
