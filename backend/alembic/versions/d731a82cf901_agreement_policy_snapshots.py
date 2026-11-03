"""Freeze quotation policy and validity context."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d731a82cf901"
down_revision = "67c3be4f761c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agreement_versions", sa.Column("policy_snapshot", postgresql.JSONB(), nullable=True))
    # Existing offers retain the policies of their associated plan at migration.
    op.execute("""UPDATE agreement_versions a SET policy_snapshot = jsonb_build_object(
        'allow_pause', p.allow_pause, 'allow_resume', p.allow_resume,
        'allow_renewal', p.allow_renewal, 'allow_early_closure', p.allow_early_closure,
        'auto_close_on_expiry', p.auto_close_on_expiry)
        FROM subscriptions s JOIN plans p ON p.id = s.plan_id WHERE a.subscription_id = s.id""")
    op.alter_column("agreement_versions", "policy_snapshot", nullable=False)
    op.add_column("agreement_versions", sa.Column("validity_days", sa.Integer(), nullable=False, server_default="30"))
    op.alter_column("agreement_versions", "validity_days", server_default=None)
    op.create_check_constraint("ck_agreement_versions_validity_nonneg", "agreement_versions", "validity_days >= 0")


def downgrade():
    op.drop_constraint("ck_agreement_versions_validity_nonneg", "agreement_versions", type_="check")
    op.drop_column("agreement_versions", "validity_days")
    op.drop_column("agreement_versions", "policy_snapshot")
