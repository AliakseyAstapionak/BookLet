"""provider no overlap

Revision ID: cce30a1c6351
Revises: 830bdb42f6bd
"""
from typing import Sequence, Union

from alembic import op

revision: str = 'cce30a1c6351'
down_revision: Union[str, Sequence[str], None] = '830bdb42f6bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    op.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT ex_provider_no_overlap
        EXCLUDE USING gist (
            provider_id WITH =,
            tstzrange(start_at, end_at, '[)') WITH &&
        )
        WHERE (status IN ('PENDING', 'CONFIRMED'));
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS ex_provider_no_overlap;")