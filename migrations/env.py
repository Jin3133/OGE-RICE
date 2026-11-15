from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool

from oge_main.infrastructure.database import models  # noqa: F401
from oge_main.infrastructure.database.base import Base
from oge_main.infrastructure.database.session import DatabaseSettings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = DatabaseSettings.from_environment()
config.set_main_option("sqlalchemy.url", settings.url.replace("%", "%%"))
target_metadata = Base.metadata


def include_application_object(obj, name, type_, reflected, compare_to) -> bool:
    """Exclude extension-owned relations from application migration diffs."""
    if reflected and compare_to is None:
        schema = getattr(obj, "schema", None)
        if schema not in (None, "public"):
            return False
        if name in {"layer", "spatial_ref_sys", "topology"}:
            return False
    return alembic_helpers.include_object(obj, name, type_, reflected, compare_to)


def configure(connection=None) -> None:
    options = {
        "target_metadata": target_metadata,
        "compare_type": True,
        "include_schemas": True,
        "include_object": include_application_object,
        "process_revision_directives": alembic_helpers.writer,
        "render_item": alembic_helpers.render_item,
    }
    if connection is None:
        context.configure(
            url=config.get_main_option("sqlalchemy.url"),
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            **options,
        )
    else:
        context.configure(connection=connection, **options)


def run_migrations_offline() -> None:
    configure()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        configure(connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
