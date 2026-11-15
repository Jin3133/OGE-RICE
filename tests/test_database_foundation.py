from __future__ import annotations

import pytest
from sqlalchemy import CheckConstraint, PrimaryKeyConstraint

from oge_main.infrastructure.database import models  # noqa: F401
from oge_main.infrastructure.database.base import NAMING_CONVENTION, Base
from oge_main.infrastructure.database.session import DatabaseSettings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OGE_DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="OGE_DATABASE_URL"):
        DatabaseSettings.from_environment()


def test_only_psycopg_postgresql_url_is_accepted() -> None:
    with pytest.raises(ValueError, match=r"postgresql\+psycopg"):
        DatabaseSettings(url="sqlite:///temporary.db")


def test_foundation_metadata_has_deterministic_constraints() -> None:
    assert NAMING_CONVENTION["pk"] == "pk_%(table_name)s"
    expected = {
        "resource_heads",
        "operations",
        "operation_attempts",
        "audit_events",
        "idempotency_records",
    }
    assert expected.issubset(Base.metadata.tables)
    resource_heads = Base.metadata.tables["resource_heads"]
    primary_key = next(
        constraint
        for constraint in resource_heads.constraints
        if isinstance(constraint, PrimaryKeyConstraint)
    )
    assert primary_key.name == "pk_resource_heads"
    checks = {
        constraint.name
        for constraint in resource_heads.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_resource_heads_current_revision_positive" in checks
