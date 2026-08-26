"""add client_incident_id to incidents

Revision ID: 3f6b24ce83e2
Revises: 2b37be4dc170
Create Date: 2026-08-26 10:32:14.979645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f6b24ce83e2'
down_revision: Union[str, Sequence[str], None] = '2b37be4dc170'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "incidents",
        sa.Column("client_incident_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_incidents_client_incident_id"),
        "incidents",
        ["client_incident_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_incidents_client_incident_id"), table_name="incidents")
    op.drop_column("incidents", "client_incident_id")
