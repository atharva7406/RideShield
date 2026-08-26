"""add decision engine fields to incidents

Revision ID: a6c093905017
Revises: 001216e07add
Create Date: 2026-08-26 11:37:44.409582

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6c093905017'
down_revision: Union[str, Sequence[str], None] = '001216e07add'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("incidents", sa.Column("window_quality", sa.String(length=20), nullable=True))
    op.add_column("incidents", sa.Column("decision_confidence", sa.String(length=20), nullable=True))
    op.add_column("incidents", sa.Column("decision_evidence", sa.String(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("incidents", "decision_evidence")
    op.drop_column("incidents", "decision_confidence")
    op.drop_column("incidents", "window_quality")
