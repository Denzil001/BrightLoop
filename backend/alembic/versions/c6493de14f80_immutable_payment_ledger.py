"""Enforce the accepted no-payment-edit/delete policy in PostgreSQL."""
from alembic import op

revision = "c6493de14f80"
down_revision = "b502c8e34a17"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION reject_payment_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Payment records are immutable' USING ERRCODE = '23514', CONSTRAINT = 'ck_payments_immutable';
        END; $$""")
    op.execute("""CREATE TRIGGER payments_immutable BEFORE UPDATE OR DELETE ON payments
        FOR EACH ROW EXECUTE FUNCTION reject_payment_mutation()""")


def downgrade():
    op.execute("DROP TRIGGER payments_immutable ON payments")
    op.execute("DROP FUNCTION reject_payment_mutation()")
