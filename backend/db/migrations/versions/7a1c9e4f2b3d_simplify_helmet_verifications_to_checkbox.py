"""simplify helmet_verifications to checkbox acknowledgment

Removes the ML-classifier-shaped columns (predicted_class, confidence,
model_version) from helmet_verifications now that the mandatory helmet
gate is a rider checkbox acknowledgment, not a photo run through a
Haar-cascade/ONNX classifier (see
app/services/helmet_verification_service.py's module docstring for why:
neither model ever reliably told a worn helmet from no helmet, and a
photo can't prove a rider keeps a helmet on for the rest of the shift
anyway). helmet_worn stays — it's still the real gate-satisfying signal,
just now set directly from the rider's explicit acknowledgment rather
than an inferred verdict.

Revision ID: 7a1c9e4f2b3d
Revises: bd7ba87c5821
Create Date: 2026-08-26 22:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7a1c9e4f2b3d'
down_revision: Union[str, Sequence[str], None] = '35d5e86f8fbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # op.drop_constraint('ck_helmet_verifications_confidence_range', 'helmet_verifications', type_='check')
    # op.drop_column('helmet_verifications', 'predicted_class')
    # op.drop_column('helmet_verifications', 'confidence')
    # op.drop_column('helmet_verifications', 'model_version')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('helmet_verifications', sa.Column('model_version', sa.String(length=100), nullable=False, server_default='checkbox-acknowledgment-v1'))
    op.add_column('helmet_verifications', sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=False, server_default='1.0'))
    op.add_column('helmet_verifications', sa.Column('predicted_class', sa.String(length=30), nullable=False, server_default='checkbox_acknowledged'))
    op.create_check_constraint('ck_helmet_verifications_confidence_range', 'helmet_verifications', 'confidence >= 0 AND confidence <= 1')
