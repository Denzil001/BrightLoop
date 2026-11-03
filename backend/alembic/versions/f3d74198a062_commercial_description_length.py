"""Composed plan/product descriptions may exceed a single catalog name."""
from alembic import op
import sqlalchemy as sa

revision = "f3d74198a062"
down_revision = "e7312d48bc50"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("agreement_lines", "snapshot_name", existing_type=sa.String(255), type_=sa.Text())
    op.alter_column("invoice_lines", "snapshot_description", existing_type=sa.String(255), type_=sa.Text())


def downgrade():
    op.alter_column("invoice_lines", "snapshot_description", existing_type=sa.Text(), type_=sa.String(255))
    op.alter_column("agreement_lines", "snapshot_name", existing_type=sa.Text(), type_=sa.String(255))
