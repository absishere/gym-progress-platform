"""initial PostgreSQL-compatible schema"""
from alembic import op
import sqlalchemy as sa


revision = "20260601_01"
down_revision = None


def upgrade() -> None:
    from models import Base
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from models import Base
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
