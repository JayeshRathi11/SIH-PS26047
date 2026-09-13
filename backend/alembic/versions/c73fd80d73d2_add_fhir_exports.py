"""add_fhir_exports

Revision ID: c73fd80d73d2
Revises: 10977d263538
Create Date: 2026-09-13 22:52:53.250047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c73fd80d73d2'
down_revision: Union[str, Sequence[str], None] = '10977d263538'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new values to privacy_audit_action_enum
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'FHIR_EXPORT_GENERATED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'HIS_EXPORT_INITIATED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'HIS_EXPORT_COMPLETED'")
    op.execute("ALTER TYPE privacy_audit_action_enum ADD VALUE IF NOT EXISTS 'HIS_EXPORT_FAILED'")

    op.create_table('fhir_exports',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('patient_id', sa.Integer(), nullable=False),
    sa.Column('interview_id', sa.Integer(), nullable=False),
    sa.Column('summary_id', sa.Integer(), nullable=True),
    sa.Column('summary_version', sa.Integer(), nullable=True),
    sa.Column('bundle_id', sa.String(length=64), nullable=False),
    sa.Column('bundle_type', sa.String(length=32), nullable=False),
    sa.Column('status', sa.Enum('GENERATED', 'TRANSMITTING', 'TRANSMITTED', 'FAILED', name='fhir_export_status_enum', create_constraint=True), nullable=False),
    sa.Column('consent_checked', sa.Boolean(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('transmitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('adapter_name', sa.String(length=64), nullable=False),
    sa.Column('environment', sa.String(length=32), nullable=False),
    sa.Column('external_reference', sa.String(length=128), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('error_message', sa.String(length=512), nullable=True),
    sa.Column('bundle_json', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['summary_id'], ['medical_case_summaries.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fhir_exports_bundle_id'), 'fhir_exports', ['bundle_id'], unique=False)
    op.create_index(op.f('ix_fhir_exports_id'), 'fhir_exports', ['id'], unique=False)
    op.create_index(op.f('ix_fhir_exports_interview_id'), 'fhir_exports', ['interview_id'], unique=False)
    op.create_index('ix_fhir_exports_interview_version_status', 'fhir_exports', ['interview_id', 'summary_version', 'status'], unique=False)
    op.create_index(op.f('ix_fhir_exports_patient_id'), 'fhir_exports', ['patient_id'], unique=False)
    op.create_index(op.f('ix_fhir_exports_status'), 'fhir_exports', ['status'], unique=False)
    op.create_index(op.f('ix_fhir_exports_summary_id'), 'fhir_exports', ['summary_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_fhir_exports_summary_id'), table_name='fhir_exports')
    op.drop_index(op.f('ix_fhir_exports_status'), table_name='fhir_exports')
    op.drop_index(op.f('ix_fhir_exports_patient_id'), table_name='fhir_exports')
    op.drop_index('ix_fhir_exports_interview_version_status', table_name='fhir_exports')
    op.drop_index(op.f('ix_fhir_exports_interview_id'), table_name='fhir_exports')
    op.drop_index(op.f('ix_fhir_exports_id'), table_name='fhir_exports')
    op.drop_index(op.f('ix_fhir_exports_bundle_id'), table_name='fhir_exports')
    op.drop_table('fhir_exports')
