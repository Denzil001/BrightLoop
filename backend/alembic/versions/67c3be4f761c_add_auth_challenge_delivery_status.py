"""add_auth_challenge_delivery_status

Revision ID: 67c3be4f761c
Revises: bc5f8296bd9e
Create Date: 2026-10-31 22:52:45.141549

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67c3be4f761c'
down_revision: Union[str, Sequence[str], None] = 'bc5f8296bd9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('auth_challenges', sa.Column('delivery_status', sa.String(length=32), server_default='PENDING', nullable=False))
    op.add_column('auth_challenges', sa.Column('delivery_attempts', sa.Integer(), server_default='0', nullable=False))
    op.create_check_constraint(
        'ck_auth_challenges_delivery_status',
        'auth_challenges',
        "delivery_status IN ('PENDING', 'SENT', 'FAILED')",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_auth_challenges_delivery_status', 'auth_challenges', type_='check')
    op.drop_column('auth_challenges', 'delivery_attempts')
    op.drop_column('auth_challenges', 'delivery_status')
