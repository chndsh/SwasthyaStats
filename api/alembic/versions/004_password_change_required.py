"""Track temporary-password accounts and refresh-token invalidation.

Revision ID: 004_password_change_required
Revises: 003_multi_user_auth
Create Date: 2026-10-24 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "004_password_change_required"
down_revision = "003_multi_user_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.alter_column("users", "must_change_password", server_default=None)
    op.add_column(
        "users",
        sa.Column("refresh_token_invalidated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "refresh_token_invalidated_at")
    op.drop_column("users", "must_change_password")
