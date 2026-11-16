"""Request-scoped infrastructure dependencies."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.orm import Session, sessionmaker

from oge_main.api.errors import ApiProblem
from oge_main.infrastructure.database.session import (
    DatabaseSettings,
    create_session_factory,
)


@lru_cache(maxsize=1)
def database_session_factory() -> sessionmaker[Session]:
    try:
        settings = DatabaseSettings.from_environment()
    except (RuntimeError, ValueError) as error:
        raise ApiProblem(
            status_code=503,
            code="DATABASE_NOT_CONFIGURED",
            message="database connection is not configured",
        ) from error
    return create_session_factory(settings)


def get_database_session():
    factory = database_session_factory()
    with factory() as session:
        yield session
