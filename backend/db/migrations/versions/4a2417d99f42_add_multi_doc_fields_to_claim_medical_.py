"""add_multi_doc_fields_to_claim_medical_reports

Revision ID: 4a2417d99f42
Revises: 35d5e86f8fbd
Create Date: 2026-08-26 19:09:56.977026

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a2417d99f42'
down_revision: Union[str, Sequence[str], None] = '35d5e86f8fbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE claim_medical_reports ADD COLUMN IF NOT EXISTS original_filename VARCHAR(255);")
    op.execute("ALTER TABLE claim_medical_reports ADD COLUMN IF NOT EXISTS mime_type VARCHAR(100);")
    op.execute("ALTER TABLE claim_medical_reports ADD COLUMN IF NOT EXISTS file_size INTEGER;")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE claim_medical_reports DROP COLUMN IF EXISTS file_size;")
    op.execute("ALTER TABLE claim_medical_reports DROP COLUMN IF EXISTS mime_type;")
    op.execute("ALTER TABLE claim_medical_reports DROP COLUMN IF EXISTS original_filename;")
