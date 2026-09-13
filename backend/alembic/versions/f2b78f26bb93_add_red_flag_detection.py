"""add_red_flag_detection

Revision ID: f2b78f26bb93
Revises: f8eec2812e08
Create Date: 2026-09-13 16:45:03.825145

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2b78f26bb93'
down_revision: Union[str, Sequence[str], None] = 'f8eec2812e08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_RED_FLAG_RULES = [
    {
        "rule_key": "severe_chest_pain",
        "name": "Severe Chest Pain / Pressure",
        "description": "Severe chest pain, crushing pressure, squeezing, or heaviness radiating to arm, neck, or jaw.",
        "severity": "CRITICAL",
        "active": True,
    },
    {
        "rule_key": "severe_dyspnea",
        "name": "Severe Difficulty Breathing",
        "description": "Severe acute shortness of breath, respiratory distress, gasping, or inability to breathe.",
        "severity": "CRITICAL",
        "active": True,
    },
    {
        "rule_key": "loss_of_consciousness",
        "name": "Loss of Consciousness / Fainting",
        "description": "Sudden syncope, blackout, unresponsiveness, or fainting episode.",
        "severity": "HIGH",
        "active": True,
    },
    {
        "rule_key": "acute_confusion",
        "name": "Acute Confusion / Altered Mental Status",
        "description": "New onset of severe confusion, delirium, disorientation, or inability to respond normally.",
        "severity": "HIGH",
        "active": True,
    },
    {
        "rule_key": "unilateral_weakness",
        "name": "Sudden Unilateral Weakness or Numbness",
        "description": "Sudden onset of weakness, paralysis, numbness, or facial drooping affecting one side of the body.",
        "severity": "CRITICAL",
        "active": True,
    },
    {
        "rule_key": "uncontrolled_bleeding",
        "name": "Severe Uncontrolled Bleeding",
        "description": "Profuse, active, continuous, or uncontrolled hemorrhage from any anatomical site.",
        "severity": "CRITICAL",
        "active": True,
    },
    {
        "rule_key": "suicidal_ideation",
        "name": "Suicidal or Self-Harm Emergency",
        "description": "Active expression of suicidal intent, desire to end life, or self-harm emergency.",
        "severity": "CRITICAL",
        "active": True,
    },
    {
        "rule_key": "anaphylaxis_warning",
        "name": "Severe Allergic Reaction / Anaphylaxis",
        "description": "Acute allergic reaction signs including airway/throat swelling, wheezing, and breathing difficulty.",
        "severity": "CRITICAL",
        "active": True,
    },
    {
        "rule_key": "seizure_convulsion",
        "name": "Seizure or Convulsion Episode",
        "description": "Recent active seizure episode, fitting, convulsions, or uncontrollable body spasms.",
        "severity": "HIGH",
        "active": True,
    },
    {
        "rule_key": "thunderclap_headache",
        "name": "Sudden Extremely Severe Headache",
        "description": "Sudden, excruciating, explosive headache reaching maximum intensity within seconds to minutes ('worst headache of life').",
        "severity": "HIGH",
        "active": True,
    },
]


def upgrade() -> None:
    # 1. Create red_flag_rules table
    rules_table = op.create_table(
        'red_flag_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rule_key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_red_flag_rules_rule_key'), 'red_flag_rules', ['rule_key'], unique=True)
    op.create_index(op.f('ix_red_flag_rules_id'), 'red_flag_rules', ['id'], unique=False)

    # 2. Seed initial 10 red flag rules
    op.bulk_insert(rules_table, DEFAULT_RED_FLAG_RULES)

    # 3. Create interview_red_flags table
    op.create_table(
        'interview_red_flags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('interview_id', sa.Integer(), nullable=False),
        sa.Column('rule_key', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('evidence', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='ACTIVE'),
        sa.Column('detected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['interview_id'], ['interviews.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rule_key'], ['red_flag_rules.rule_key'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_interview_red_flags_id'), 'interview_red_flags', ['id'], unique=False)
    op.create_index(op.f('ix_interview_red_flags_interview_id'), 'interview_red_flags', ['interview_id'], unique=False)
    op.create_index(op.f('ix_interview_red_flags_rule_key'), 'interview_red_flags', ['rule_key'], unique=False)
    op.create_index(op.f('ix_interview_red_flags_status'), 'interview_red_flags', ['status'], unique=False)

    # 4. Partial unique index: prevent duplicate active or acknowledged detections for same interview and rule
    op.create_index(
        'ix_active_interview_rule_detection',
        'interview_red_flags',
        ['interview_id', 'rule_key'],
        unique=True,
        postgresql_where=sa.text("status IN ('ACTIVE', 'ACKNOWLEDGED')"),
    )


def downgrade() -> None:
    op.drop_index('ix_active_interview_rule_detection', table_name='interview_red_flags')
    op.drop_index(op.f('ix_interview_red_flags_status'), table_name='interview_red_flags')
    op.drop_index(op.f('ix_interview_red_flags_rule_key'), table_name='interview_red_flags')
    op.drop_index(op.f('ix_interview_red_flags_interview_id'), table_name='interview_red_flags')
    op.drop_index(op.f('ix_interview_red_flags_id'), table_name='interview_red_flags')
    op.drop_table('interview_red_flags')

    op.drop_index(op.f('ix_red_flag_rules_id'), table_name='red_flag_rules')
    op.drop_index(op.f('ix_red_flag_rules_rule_key'), table_name='red_flag_rules')
    op.drop_table('red_flag_rules')
