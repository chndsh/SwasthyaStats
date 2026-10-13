"""Initial schema baseline

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-13 18:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # patients
    op.create_table(
        'patients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_patients_id', 'patients', ['id'], unique=False)

    # app_settings
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_secret', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )

    # documents
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('doc_type', sa.String(length=50), nullable=True),
        sa.Column('doc_date', sa.Date(), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('ocr_lines', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_id', 'documents', ['id'], unique=False)
    op.create_index('ix_documents_patient_id', 'documents', ['patient_id'], unique=False)
    op.create_index('ix_documents_sha256', 'documents', ['sha256'], unique=False)
    op.create_index('ix_documents_status', 'documents', ['status'], unique=False)

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
        sa.Column('raw_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('field_confidence', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reviewer_edits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_extractions_id', 'extractions', ['id'], unique=False)
    op.create_index('ix_extractions_document_id', 'extractions', ['document_id'], unique=False)

    # observations
    op.create_table(
        'observations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('test_name', sa.String(length=255), nullable=False),
        sa.Column('canonical_test_id', sa.String(length=100), nullable=True),
        sa.Column('value_num', sa.Float(), nullable=True),
        sa.Column('value_text', sa.String(length=100), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('ref_low', sa.Float(), nullable=True),
        sa.Column('ref_high', sa.Float(), nullable=True),
        sa.Column('flag', sa.String(length=20), nullable=True),
        sa.Column('collected_at', sa.Date(), nullable=True),
        sa.Column('page_no', sa.Integer(), nullable=False),
        sa.Column('source_line_ids', sa.ARRAY(sa.Integer()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_observations_id', 'observations', ['id'], unique=False)
    op.create_index('ix_observations_patient_id', 'observations', ['patient_id'], unique=False)
    op.create_index('ix_observations_document_id', 'observations', ['document_id'], unique=False)
    op.create_index('ix_observations_status', 'observations', ['status'], unique=False)
    op.create_index('ix_observations_canonical_test_id', 'observations', ['canonical_test_id'], unique=False)

    # chunks
    op.create_table(
        'chunks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embed_model', sa.String(length=100), nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('page', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chunks_id', 'chunks', ['id'], unique=False)
    op.create_index('ix_chunks_document_id', 'chunks', ['document_id'], unique=False)

    # llm_calls
    op.create_table(
        'llm_calls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('key_label', sa.String(length=100), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_llm_calls_id', 'llm_calls', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('llm_calls')
    op.drop_table('chunks')
    op.drop_table('observations')
    op.drop_table('extractions')
    op.drop_table('document_pages')
    op.drop_table('documents')
    op.drop_table('app_settings')
    op.drop_table('patients')
