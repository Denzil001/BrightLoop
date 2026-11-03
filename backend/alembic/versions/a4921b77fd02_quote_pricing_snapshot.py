"""Preserve the displayed quotation estimate alongside authoritative line snapshots."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a4921b77fd02"
down_revision = "d731a82cf901"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agreement_versions", sa.Column("pricing_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"))
    op.alter_column("agreement_versions", "pricing_snapshot", server_default=None)


def downgrade():
    op.drop_column("agreement_versions", "pricing_snapshot")
