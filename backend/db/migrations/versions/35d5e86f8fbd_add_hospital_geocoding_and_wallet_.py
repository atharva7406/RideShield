"""add hospital geocoding and wallet recharge payment type

Revision ID: 35d5e86f8fbd
Revises: a6c093905017
Create Date: 2026-08-26 16:01:54.052464

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35d5e86f8fbd'
down_revision: Union[str, Sequence[str], None] = 'a6c093905017'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Additive-only, matching the teammate's L2/L3/claims/hospital/wallet-
    recharge features (see backend/app/api/auth.py's hospital geocoding on
    HOSPITAL_REP registration, and payments.py's WALLET_RECHARGE path).
    Written as a raw-SQL idempotent patch — not a plain op.add_column/
    op.add_column-style migration — because these exact changes were
    already applied directly to the shared dev DB by the teammate's
    now-removed main.py:run_db_patches() (a startup-time raw-SQL patch,
    replaced by this proper migration per the decision to stop bypassing
    Alembic). IF NOT EXISTS / IF EXISTS guards make this a safe no-op
    there, while still being a real migration for anyone building the DB
    from scratch.
    """
    op.execute("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS latitude FLOAT")
    op.execute("ALTER TABLE hospitals ADD COLUMN IF NOT EXISTS longitude FLOAT")
    op.execute("ALTER TABLE hospitals ALTER COLUMN locality TYPE VARCHAR(500)")

    op.execute("ALTER TYPE payment_type_enum ADD VALUE IF NOT EXISTS 'WALLET_RECHARGE'")

    # WALLET_RECHARGE payments have neither shift_id nor claim_id, so the
    # old two-way linkage constraint no longer holds for every payment_type.
    op.execute("ALTER TABLE payments DROP CONSTRAINT IF EXISTS ck_payments_type_linkage")


def downgrade() -> None:
    """Downgrade schema.

    Note: Postgres cannot remove a value from an existing enum type, so
    'WALLET_RECHARGE' is NOT removed from payment_type_enum here — that's
    a one-way door in Postgres, not something this migration can undo
    safely (would require rebuilding the whole enum type and every column
    using it). Everything else is reversed.
    """
    op.execute(
        "ALTER TABLE payments ADD CONSTRAINT ck_payments_type_linkage "
        "CHECK ((payment_type = 'PREMIUM_COLLECTION' AND shift_id IS NOT NULL) "
        "OR (payment_type = 'CLAIM_PAYOUT' AND claim_id IS NOT NULL))"
    )
    op.execute("ALTER TABLE hospitals ALTER COLUMN locality TYPE VARCHAR(100)")
    op.execute("ALTER TABLE hospitals DROP COLUMN IF EXISTS longitude")
    op.execute("ALTER TABLE hospitals DROP COLUMN IF EXISTS latitude")
