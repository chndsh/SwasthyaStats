"""Add doctor_name column to documents table

Revision ID: 002_add_doctor_name
Revises: 001_initial_schema
Create Date: 2026-10-23 08:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '002_add_doctor_name'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('documents')]
    if 'doctor_name' not in columns:
        op.add_column('documents', sa.Column('doctor_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('documents')]
    if 'doctor_name' in columns:
        op.drop_column('documents', 'doctor_name')
