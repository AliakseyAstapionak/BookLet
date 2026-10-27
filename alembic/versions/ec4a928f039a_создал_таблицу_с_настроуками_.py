"""создал таблицу с настроуками пользователя и удалил _2fa из users

Revision ID: ec4a928f039a
Revises: 
Create Date: 2026-10-27 21:52:33.178257

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec4a928f039a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.create_table(
        'user_settings',
        sa.Column('user_id', sa.Integer(), primary_key=True),
        sa.Column('two_factor_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('show_email', sa.Boolean(), server_default='false', nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    op.execute("""
        INSERT INTO user_settings (user_id, two_factor_enabled)
        SELECT id, _2fa FROM users;
    """)

    op.drop_column('users', '_2fa')


def downgrade():
    op.add_column('users', sa.Column('_2fa', sa.Boolean(), server_default='false', nullable=True))

    op.execute("""
        UPDATE users 
        SET _2fa = user_settings.two_factor_enabled 
        FROM user_settings 
        WHERE users.id = user_settings.user_id;
    """)

    op.drop_table('user_settings')