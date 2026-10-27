"""создал таблицу с настроуками пользователя и удалил _2fa из users 2 попытка

Revision ID: 452f3b27c717
Revises: ec4a928f039a
Create Date: 2026-10-27 22:11:01.014599

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '452f3b27c717'
down_revision: Union[str, Sequence[str], None] = 'ec4a928f039a'
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
        INSERT INTO user_settings (user_id)
        SELECT id FROM users;
    """)




def downgrade():
    op.add_column('users', sa.Column('_2fa', sa.Boolean(), server_default='false', nullable=True))

    op.execute("""
        UPDATE users 
        SET _2fa = user_settings.two_factor_enabled 
        FROM user_settings 
        WHERE users.id = user_settings.user_id;
    """)

    op.drop_table('user_settings')
