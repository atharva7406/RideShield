"""add_razorpay_fields_to_payment

Revision ID: 7c45f2aef123
Revises: 6b34e1bddbee
Create Date: 2026-08-23 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c45f2aef123'
down_revision: Union[str, Sequence[str], None] = '6b34e1bddbee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('payments', sa.Column('razorpay_order_id', sa.String(length=100), nullable=True))
    op.add_column('payments', sa.Column('razorpay_signature', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_payments_razorpay_order_id'), 'payments', ['razorpay_order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_razorpay_order_id'), table_name='payments')
    op.drop_column('payments', 'razorpay_signature')
    op.drop_column('payments', 'razorpay_order_id')
