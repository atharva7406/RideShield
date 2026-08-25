"""merge hospital features and helmet verifications branches

Revision ID: 2b37be4dc170
Revises: 898d5c82409e, bd7ba87c5821
Create Date: 2026-08-26 02:43:10.689767

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b37be4dc170'
down_revision: Union[str, Sequence[str], None] = ('898d5c82409e', 'bd7ba87c5821')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
