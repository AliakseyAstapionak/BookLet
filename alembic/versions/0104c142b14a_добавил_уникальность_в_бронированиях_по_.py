"""добавил уникальность в бронированиях по айди провайдера и пересечению времени 

Revision ID: 0104c142b14a
Revises: cce30a1c6351
Create Date: 2026-10-30 13:33:06.457522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0104c142b14a'
down_revision: Union[str, Sequence[str], None] = 'cce30a1c6351'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS ex_provider_no_overlap;")
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