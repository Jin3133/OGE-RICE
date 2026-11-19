"""Allow review-required rice-field candidate results.

Revision ID: 20261120_01
Revises: d6e6f8a4fb04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261120_01"
down_revision: str | Sequence[str] | None = "d6e6f8a4fb04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_remote_sensing_result_versions_target_supported"),
        "remote_sensing_result_versions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_remote_sensing_result_versions_target_supported"),
        "remote_sensing_result_versions",
        "target IN ('cultivated_land_candidate', 'rice_field_candidate')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_remote_sensing_result_versions_target_supported"),
        "remote_sensing_result_versions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_remote_sensing_result_versions_target_supported"),
        "remote_sensing_result_versions",
        "target = 'cultivated_land_candidate'",
    )
