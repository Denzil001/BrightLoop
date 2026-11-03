"""Share authentication rate limits across API workers."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e90c51fa2b73"
down_revision = "d8a149c27e60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("rate_limit_windows",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("attempts", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_rate_limit_windows_updated_at", "rate_limit_windows", ["updated_at"])


def downgrade():
    op.drop_table("rate_limit_windows")
