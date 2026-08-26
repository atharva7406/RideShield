"""make client_incident_id unique on incidents

Revision ID: 001216e07add
Revises: 3f6b24ce83e2
Create Date: 2026-08-26 10:55:26.862977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001216e07add'
down_revision: Union[str, Sequence[str], None] = '3f6b24ce83e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Postgres unique indexes treat NULLs as distinct (never conflict with
    # each other), so a plain unique index is correct here — old rows and
    # any future submission with no client_incident_id are unaffected.
    op.drop_index(op.f("ix_incidents_client_incident_id"), table_name="incidents")
    op.create_index(
        op.f("ix_incidents_client_incident_id"),
        "incidents",
        ["client_incident_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_incidents_client_incident_id"), table_name="incidents")
    op.create_index(
        op.f("ix_incidents_client_incident_id"),
        "incidents",
        ["client_incident_id"],
        unique=False,
    )
