"""add_analytics_indexes

Revision ID: 5d6e226b7e3d
Revises: 726ab9fadc71
Create Date: 2026-09-13 23:17:31.383177

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d6e226b7e3d'
down_revision: Union[str, Sequence[str], None] = '726ab9fadc71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index('ix_interviews_created_at', 'interviews', ['created_at'], unique=False)
    op.create_index('ix_patients_created_at', 'patients', ['created_at'], unique=False)
    op.create_index('ix_medical_documents_uploaded_at', 'medical_documents', ['uploaded_at'], unique=False)
    op.create_index('ix_medical_case_summaries_created_at', 'medical_case_summaries', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_medical_case_summaries_created_at', table_name='medical_case_summaries')
    op.drop_index('ix_medical_documents_uploaded_at', table_name='medical_documents')
    op.drop_index('ix_patients_created_at', table_name='patients')
    op.drop_index('ix_interviews_created_at', table_name='interviews')
