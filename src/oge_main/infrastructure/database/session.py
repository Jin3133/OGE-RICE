"""Database configuration and synchronous Session construction."""

from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    url: str
    pool_pre_ping: bool = True

    def __post_init__(self) -> None:
        if not self.url.startswith("postgresql+psycopg://"):
            raise ValueError("database URL must use the postgresql+psycopg driver")

    @classmethod
    def from_environment(cls, variable: str = "OGE_DATABASE_URL") -> DatabaseSettings:
        value = os.getenv(variable)
        if not value:
            raise RuntimeError(f"required database setting {variable} is not configured")
        return cls(url=value)


def create_database_engine(settings: DatabaseSettings) -> Engine:
    return create_engine(
        settings.url,
        pool_pre_ping=settings.pool_pre_ping,
        future=True,
    )


def create_session_factory(
    settings: DatabaseSettings,
) -> sessionmaker[Session]:
    engine = create_database_engine(settings)
    return sessionmaker(
        bind=engine,
        class_=Session,
        autoflush=True,
        expire_on_commit=False,
    )
