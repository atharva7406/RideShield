"""merge heads

Revision ID: 394da2cfd515
Revises: 76fc1d3732e4, 7a1c9e4f2b3d
Create Date: 2026-08-27 00:21:24.794447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '394da2cfd515'
down_revision: Union[str, Sequence[str], None] = ('76fc1d3732e4', '7a1c9e4f2b3d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
