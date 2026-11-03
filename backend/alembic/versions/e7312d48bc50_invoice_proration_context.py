"""Record actual/full service days for reproducible partial-period documents."""
from alembic import op
import sqlalchemy as sa

revision = "e7312d48bc50"
down_revision = "a4921b77fd02"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("invoices", sa.Column("full_period_end", sa.Date(), nullable=True))
    op.add_column("invoices", sa.Column("service_days", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("invoices", sa.Column("full_period_days", sa.Integer(), nullable=False, server_default="1"))
    op.execute("UPDATE invoices SET full_period_end = period_end, service_days = period_end - period_start, full_period_days = period_end - period_start")
    op.alter_column("invoices", "service_days", server_default=None)
    op.alter_column("invoices", "full_period_days", server_default=None)
    op.create_check_constraint("ck_invoices_proration_days", "invoices", "service_days > 0 AND full_period_days >= service_days")


def downgrade():
    op.drop_constraint("ck_invoices_proration_days", "invoices", type_="check")
    for name in ("full_period_days", "service_days", "full_period_end"):
        op.drop_column("invoices", name)
