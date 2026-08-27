"""add_structured_fields_to_claim_medical_reports

Revision ID: 76fc1d3732e4
Revises: 66f48f664e78
Create Date: 2026-08-26 21:31:09.959895

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76fc1d3732e4'
down_revision: Union[str, Sequence[str], None] = '66f48f664e78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('claim_medical_reports', sa.Column('patient_identifier', sa.String(255), nullable=True))
    op.add_column('claim_medical_reports', sa.Column('facility_name', sa.String(255), nullable=True))
    op.add_column('claim_medical_reports', sa.Column('hospital_locality', sa.String(100), nullable=True))
    op.add_column('claim_medical_reports', sa.Column('admittance_timestamp', sa.DateTime(timezone=True), nullable=True))
    op.add_column('claim_medical_reports', sa.Column('diagnosis_notes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('claim_medical_reports', 'diagnosis_notes')
    op.drop_column('claim_medical_reports', 'admittance_timestamp')
    op.drop_column('claim_medical_reports', 'hospital_locality')
    op.drop_column('claim_medical_reports', 'facility_name')
    op.drop_column('claim_medical_reports', 'patient_identifier')
