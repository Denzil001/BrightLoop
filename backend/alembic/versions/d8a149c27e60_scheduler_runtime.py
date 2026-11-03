"""Persist scheduler heartbeat and bounded scan continuation."""
from alembic import op
import sqlalchemy as sa

revision = "d8a149c27e60"
down_revision = "c6493de14f80"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("scheduler_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_id", sa.Uuid(), sa.ForeignKey("billing_runs.id", ondelete="RESTRICT")),
        sa.Column("continue_after_id", sa.Uuid()),
        sa.Column("safe_error_code", sa.String(64)),
        sa.CheckConstraint("id = 1", name="ck_scheduler_singleton"),
        sa.CheckConstraint("state IN ('RUNNING', 'IDLE', 'FAILED', 'STOPPED')", name="ck_scheduler_state"),
        sa.CheckConstraint("interval_seconds BETWEEN 10 AND 86400", name="ck_scheduler_interval"))


def downgrade():
    op.drop_table("scheduler_state")
