"""add_app_users

Step 17: Authentication & RBAC layer.

Creates the app_users table with:
- id, email (unique), password_hash
- role enum (PATIENT | DOCTOR | STAFF | ADMIN)
- patient_id (nullable FK → patients.id, SET NULL on delete)
- is_active, created_at, updated_at

Revision ID: a1b2c3d4e5f6
Revises: 6d7e8f9a0b1c
Create Date: 2026-09-14

Implementation note on enum creation:
  SQLAlchemy's sa.Enum fires a _on_table_create event that issues CREATE TYPE
  even when the type was already created.  Using the dialect-specific
  PgEnum(..., create_type=False) suppresses those automatic DDL events so we
  can manage the type lifecycle ourselves with plain op.execute() calls.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision = "a1b2c3d4e5f6"
down_revision = "6d7e8f9a0b1c"
branch_labels = None
depends_on = None

_ENUM_NAME = "user_role_enum"

# PgEnum with create_type=False: no automatic CREATE/DROP TYPE DDL events.
_role_col_type = PgEnum(
    "PATIENT", "DOCTOR", "STAFF", "ADMIN",
    name=_ENUM_NAME,
    create_type=False,
)


def upgrade() -> None:
    # Step 1 — create the Postgres enum type explicitly.
    op.execute(
        "CREATE TYPE user_role_enum AS ENUM "
        "('PATIENT', 'DOCTOR', 'STAFF', 'ADMIN')"
    )

    # Step 2 — create the table (enum type already exists; create_type=False
    # prevents SQLAlchemy from trying to create it again).
    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", _role_col_type, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
            ondelete="SET NULL",
        ),
    )

    op.create_index("ix_app_users_id", "app_users", ["id"])
    op.create_index("ix_app_users_email", "app_users", ["email"], unique=True)
    op.create_index("ix_app_users_role", "app_users", ["role"])
    op.create_index("ix_app_users_patient_id", "app_users", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_app_users_patient_id", table_name="app_users")
    op.drop_index("ix_app_users_role", table_name="app_users")
    op.drop_index("ix_app_users_email", table_name="app_users")
    op.drop_index("ix_app_users_id", table_name="app_users")
    op.drop_table("app_users")
    op.execute("DROP TYPE IF EXISTS user_role_enum")
