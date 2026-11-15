"""Create PostGIS extensions and persistence infrastructure tables.

Revision ID: 20261115_01
Revises: None
Create Date: 2026-11-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261115_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "resource_heads",
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "current_revision >= 1", name="ck_resource_heads_current_revision_positive"
        ),
        sa.PrimaryKeyConstraint(
            "resource_type", "resource_id", name="pk_resource_heads"
        ),
    )
    op.create_table(
        "operations",
        sa.Column("operation_id", sa.String(length=100), nullable=False),
        sa.Column("operation_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("submitted_by", sa.String(length=100), nullable=False),
        sa.Column("target_resource_type", sa.String(length=50), nullable=True),
        sa.Column("target_resource_id", sa.String(length=100), nullable=True),
        sa.Column("target_revision", sa.Integer(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_operations_status_allowed",
        ),
        sa.CheckConstraint(
            "target_revision IS NULL OR target_revision >= 1",
            name="ck_operations_target_revision_positive",
        ),
        sa.PrimaryKeyConstraint("operation_id", name="pk_operations"),
    )
    op.create_index("ix_operations_operation_type", "operations", ["operation_type"])
    op.create_index("ix_operations_status", "operations", ["status"])
    op.create_table(
        "operation_attempts",
        sa.Column("operation_id", sa.String(length=100), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("log_reference", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "attempt_number >= 1",
            name="ck_operation_attempts_attempt_number_positive",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_operation_attempts_status_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operations.operation_id"],
            name="fk_operation_attempts_operation_id_operations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "operation_id", "attempt_number", name="pk_operation_attempts"
        ),
    )
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=False),
        sa.Column("resource_revision", sa.Integer(), nullable=True),
        sa.Column(
            "summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.CheckConstraint(
            "resource_revision IS NULL OR resource_revision >= 1",
            name="ck_audit_events_resource_revision_positive",
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("actor_id", sa.String(length=100), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("resource_revision", sa.Integer(), nullable=True),
        sa.Column(
            "response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="ck_idempotency_records_status_allowed",
        ),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'",
            name="ck_idempotency_records_request_hash_sha256",
        ),
        sa.CheckConstraint(
            "resource_revision IS NULL OR resource_revision >= 1",
            name="ck_idempotency_records_resource_revision_positive",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_idempotency_records_expires_after_creation",
        ),
        sa.PrimaryKeyConstraint(
            "actor_id", "idempotency_key", name="pk_idempotency_records"
        ),
    )
    op.create_index(
        "ix_idempotency_records_expires_at", "idempotency_records", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_expires_at", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_table("operation_attempts")
    op.drop_index("ix_operations_status", table_name="operations")
    op.drop_index("ix_operations_operation_type", table_name="operations")
    op.drop_table("operations")
    op.drop_table("resource_heads")
    # Extensions are shared database capabilities and are intentionally retained.
