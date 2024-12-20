# SPDX-FileCopyrightText: © 2023 iameru
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""add Scheduler relevant tables

Revision ID: 5d2aefe5f0ad
Revises: 8d7e440490bf
Create Date: 2023-12-14 11:18:16.796182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5d2aefe5f0ad'
down_revision: Union[str, None] = '8d7e440490bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('queued_calls',
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('phone_number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('is_postponed', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('phone_number')
    )
    op.create_index(op.f('ix_queued_calls_created_at'), 'queued_calls', ['created_at'], unique=False)
    op.create_table('scheduled_calls',
    sa.Column('phone_number', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('day', sa.Integer(), nullable=False),
    sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('last_queued_at', sa.Date(), nullable=True),
    sa.Column('postponed_to', sa.DateTime(), nullable=True),
    sa.Column('last_postpone_queued_at', sa.Date(), nullable=True),
    sa.PrimaryKeyConstraint('phone_number', 'day')
    )
    op.add_column('calls', sa.Column('type', sa.Enum('INSTANT', 'SCHEDULED', name='calltype'), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('calls', 'type')
    op.drop_table('scheduled_calls')
    op.drop_index(op.f('ix_queued_calls_created_at'), table_name='queued_calls')
    op.drop_table('queued_calls')
    # ### end Alembic commands ###
