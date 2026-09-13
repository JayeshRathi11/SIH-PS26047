"""add_accessibility_support

Revision ID: 726ab9fadc71
Revises: c73fd80d73d2
Create Date: 2026-09-13 23:08:33.310745

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '726ab9fadc71'
down_revision: Union[str, Sequence[str], None] = 'c73fd80d73d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create patient_accessibility_profiles
    op.create_table(
        'patient_accessibility_profiles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('large_controls_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('high_contrast_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('audio_guidance_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('voice_input_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('touch_input_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('simplified_language_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('minimal_typing_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('pictogram_support_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('preferred_interaction_mode', sa.String(length=20), server_default='VOICE_AND_TOUCH', nullable=False),
        sa.Column('audio_speed', sa.String(length=20), server_default='NORMAL', nullable=False),
        sa.Column('accessibility_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('patient_id', name='uq_patient_accessibility_profile_patient_id'),
    )
    op.create_index(op.f('ix_patient_accessibility_profiles_id'), 'patient_accessibility_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_patient_accessibility_profiles_patient_id'), 'patient_accessibility_profiles', ['patient_id'], unique=True)

    # 2. Create accessibility_interaction_events
    op.create_table(
        'accessibility_interaction_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_accessibility_interaction_events_id'), 'accessibility_interaction_events', ['id'], unique=False)
    op.create_index(op.f('ix_accessibility_interaction_events_patient_id'), 'accessibility_interaction_events', ['patient_id'], unique=False)
    op.create_index(op.f('ix_accessibility_interaction_events_interview_id'), 'accessibility_interaction_events', ['interview_id'], unique=False)
    op.create_index(op.f('ix_accessibility_interaction_events_event_type'), 'accessibility_interaction_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_accessibility_interaction_events_created_at'), 'accessibility_interaction_events', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_accessibility_interaction_events_created_at'), table_name='accessibility_interaction_events')
    op.drop_index(op.f('ix_accessibility_interaction_events_event_type'), table_name='accessibility_interaction_events')
    op.drop_index(op.f('ix_accessibility_interaction_events_interview_id'), table_name='accessibility_interaction_events')
    op.drop_index(op.f('ix_accessibility_interaction_events_patient_id'), table_name='accessibility_interaction_events')
    op.drop_index(op.f('ix_accessibility_interaction_events_id'), table_name='accessibility_interaction_events')
    op.drop_table('accessibility_interaction_events')

    op.drop_index(op.f('ix_patient_accessibility_profiles_patient_id'), table_name='patient_accessibility_profiles')
    op.drop_index(op.f('ix_patient_accessibility_profiles_id'), table_name='patient_accessibility_profiles')
    op.drop_table('patient_accessibility_profiles')
