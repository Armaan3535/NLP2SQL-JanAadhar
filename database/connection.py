from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from database.models import Base


def get_engine(database_url: str | None = None):
    return create_engine(database_url or settings.database_url, future=True)


def create_tables(database_url: str | None = None) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(get_engine(database_url))


def recreate_tables(database_url: str | None = None) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = get_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def get_session(database_url: str | None = None) -> Session:
    factory = sessionmaker(bind=get_engine(database_url), future=True)
    return factory()
