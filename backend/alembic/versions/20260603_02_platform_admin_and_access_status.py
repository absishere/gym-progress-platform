"""platform admin and gym access status"""
from alembic import op
import sqlalchemy as sa


revision = "20260603_02"
down_revision = "20260601_01"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    gym_columns = {column["name"] for column in inspector.get_columns("gyms")}
    if "account_status" not in gym_columns:
        op.add_column("gyms", sa.Column("account_status", sa.String(length=30), nullable=False, server_default="active"))
        op.alter_column("gyms", "account_status", server_default=None)
    if "sales_channel" not in gym_columns:
        op.add_column("gyms", sa.Column("sales_channel", sa.String(length=30), nullable=False, server_default="direct"))
        op.alter_column("gyms", "sales_channel", server_default=None)
    if "access_expires_on" not in gym_columns:
        op.add_column("gyms", sa.Column("access_expires_on", sa.Date(), nullable=True))

    tables = set(inspector.get_table_names())
    if "platform_admins" not in tables:
        op.create_table(
            "platform_admins",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("phone", sa.String(length=20), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("phone"),
        )
        op.create_index("ix_platform_admins_phone", "platform_admins", ["phone"])

    if "platform_sessions" not in tables:
        op.create_table(
            "platform_sessions",
            sa.Column("token", sa.String(length=64), nullable=False),
            sa.Column("admin_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["admin_id"], ["platform_admins.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("token"),
        )
        op.create_index("ix_platform_sessions_admin_id", "platform_sessions", ["admin_id"])
        op.create_index("ix_platform_sessions_expires_at", "platform_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_platform_sessions_expires_at", table_name="platform_sessions")
    op.drop_index("ix_platform_sessions_admin_id", table_name="platform_sessions")
    op.drop_table("platform_sessions")
    op.drop_index("ix_platform_admins_phone", table_name="platform_admins")
    op.drop_table("platform_admins")
    op.drop_column("gyms", "access_expires_on")
    op.drop_column("gyms", "sales_channel")
    op.drop_column("gyms", "account_status")
