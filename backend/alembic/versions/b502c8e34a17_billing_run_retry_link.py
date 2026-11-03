"""Link recovery/continuation runs to their preceding run."""
from alembic import op
import sqlalchemy as sa

revision = "b502c8e34a17"
down_revision = "f3d74198a062"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("billing_runs", sa.Column("retry_of_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_billing_runs_retry_of", "billing_runs", "billing_runs", ["retry_of_id"], ["id"], ondelete="RESTRICT")


def downgrade():
    op.drop_constraint("fk_billing_runs_retry_of", "billing_runs", type_="foreignkey")
    op.drop_column("billing_runs", "retry_of_id")
