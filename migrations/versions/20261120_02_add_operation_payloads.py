"""Persist pipeline operation inputs and outputs.

Revision ID: 20261120_02
Revises: 20261120_01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261120_02"
down_revision: str | Sequence[str] | None = "20261120_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "operations",
        sa.Column(
            "request_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "operations",
        sa.Column(
            "result_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.alter_column("operations", "request_payload", server_default=None)


def downgrade() -> None:
    op.drop_column("operations", "result_summary")
    op.drop_column("operations", "request_payload")
