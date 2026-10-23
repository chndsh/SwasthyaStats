"""Multi user auth schema with RLS and user settings

Revision ID: 003_multi_user_auth
Revises: 002_add_doctor_name
Create Date: 2026-10-23 16:32:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = '003_multi_user_auth'
down_revision = '002_add_doctor_name'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean slate: drop legacy tables if they exist
    op.execute("DROP TABLE IF EXISTS chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS observations CASCADE")
    op.execute("DROP TABLE IF EXISTS extractions CASCADE")
    op.execute("DROP TABLE IF EXISTS document_pages CASCADE")
    op.execute("DROP TABLE IF EXISTS documents CASCADE")
    op.execute("DROP TABLE IF EXISTS app_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS patients CASCADE")
    op.execute("DROP TABLE IF EXISTS llm_calls CASCADE")
    op.execute("DROP TABLE IF EXISTS user_settings CASCADE")
    op.execute("DROP TABLE IF EXISTS refresh_token_blocklist CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")

    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_id', 'users', ['id'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # refresh_token_blocklist
    op.create_table(
        'refresh_token_blocklist',
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index('ix_refresh_token_blocklist_expires_at', 'refresh_token_blocklist', ['expires_at'], unique=False)

    # user_settings
    op.create_table(
        'user_settings',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_secret', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'key')
    )

    # documents
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='queued', nullable=False),
        sa.Column('doc_type', sa.String(length=50), server_default='lab_report', nullable=True),
        sa.Column('doctor_name', sa.String(length=255), nullable=True),
        sa.Column('doc_date', sa.Date(), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('ocr_lines', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('page_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_id', 'documents', ['id'], unique=False)
    op.create_index('ix_documents_user_id', 'documents', ['user_id'], unique=False)
    op.create_index('ix_documents_sha256', 'documents', ['sha256'], unique=False)
    op.create_index('ix_documents_status', 'documents', ['status'], unique=False)
    op.create_index('ix_documents_created_at', 'documents', ['created_at'], unique=False)

    # document_pages
    op.create_table(
        'document_pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('page_no', sa.Integer(), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('image_path', sa.String(length=500), nullable=False),
        sa.Column('original_path', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_document_pages_id', 'document_pages', ['id'], unique=False)
    op.create_index('ix_document_pages_document_id', 'document_pages', ['document_id'], unique=False)

    # extractions
    op.create_table(
        'extractions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_version', sa.String(length=50), nullable=False),
        sa.Column('structured_mode', sa.String(length=50), nullable=True),
        sa.Column('input_hash', sa.String(length=64), nullable=True),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.Column('field_confidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reviewer_edits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_extractions_id', 'extractions', ['id'], unique=False)
    op.create_index('ix_extractions_document_id', 'extractions', ['document_id'], unique=False)
    op.create_index('ix_extractions_input_hash', 'extractions', ['input_hash'], unique=False)

    # observations
    op.create_table(
        'observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('test_name', sa.String(length=255), nullable=False),
        sa.Column('canonical_test_id', sa.String(length=100), nullable=True),
        sa.Column('value_num', sa.Float(), nullable=True),
        sa.Column('value_text', sa.String(length=255), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('ref_low', sa.Float(), nullable=True),
        sa.Column('ref_high', sa.Float(), nullable=True),
        sa.Column('flag', sa.String(length=20), nullable=True),
        sa.Column('collected_at', sa.Date(), nullable=True),
        sa.Column('page_no', sa.Integer(), server_default='1', nullable=False),
        sa.Column('source_line_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_observations_id', 'observations', ['id'], unique=False)
    op.create_index('ix_observations_user_id', 'observations', ['user_id'], unique=False)
    op.create_index('ix_observations_document_id', 'observations', ['document_id'], unique=False)
    op.create_index('ix_observations_test_name', 'observations', ['test_name'], unique=False)
    op.create_index('ix_observations_canonical_test_id', 'observations', ['canonical_test_id'], unique=False)
    op.create_index('ix_observations_collected_at', 'observations', ['collected_at'], unique=False)
    op.create_index('ix_observations_status', 'observations', ['status'], unique=False)

    # chunks
    op.create_table(
        'chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embed_model', sa.String(length=100), nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('page', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chunks_id', 'chunks', ['id'], unique=False)
    op.create_index('ix_chunks_user_id', 'chunks', ['user_id'], unique=False)
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'], unique=False)

    # llm_calls
    op.create_table(
        'llm_calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('purpose', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('key_label', sa.String(length=100), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('completion_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('latency_ms', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_llm_calls_id', 'llm_calls', ['id'], unique=False)
    op.create_index('ix_llm_calls_user_id', 'llm_calls', ['user_id'], unique=False)
    op.create_index('ix_llm_calls_created_at', 'llm_calls', ['created_at'], unique=False)

    # Row Level Security (RLS)
    for table_name in ['documents', 'observations', 'chunks', 'user_settings']:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        # Allow superuser / non-tenant fallback or matched user_id
        op.execute(f"""
            CREATE POLICY {table_name}_isolation ON {table_name}
            AS PERMISSIVE
            FOR ALL
            USING (
                NULLIF(current_setting('app.current_user_id', true), '') IS NULL
                OR NULLIF(current_setting('app.current_user_id', true), '') = '-1'
                OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
            )
            WITH CHECK (
                NULLIF(current_setting('app.current_user_id', true), '') IS NULL
                OR NULLIF(current_setting('app.current_user_id', true), '') = '-1'
                OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::integer
            );
        """)


def downgrade() -> None:
    raise NotImplementedError("Clean slate migration cannot be downgraded.")
