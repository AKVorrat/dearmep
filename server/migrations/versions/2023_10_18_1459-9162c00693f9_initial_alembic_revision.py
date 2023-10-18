"""initial alembic revision

Revision ID: 9162c00693f9
Revises:
Create Date: 2023-10-18 14:59:13.969344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9162c00693f9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('blobs',
    sa.Column('modified_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('mime_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('etag', sqlmodel.sql.sqltypes.GUID(), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_blobs_type'), 'blobs', ['type'], unique=False)
    op.create_table('medialists',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('items', sa.JSON(), nullable=True),
    sa.Column('format', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('mimetype', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_medialists_created_at'), 'medialists', ['created_at'], unique=False)
    op.create_table('number_verification_requests',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('requested_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('failed_attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('ignore', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_number_verification_requests_completed_at'), 'number_verification_requests', ['completed_at'], unique=False)
    op.create_index(op.f('ix_number_verification_requests_requested_at'), 'number_verification_requests', ['requested_at'], unique=False)
    op.create_index(op.f('ix_number_verification_requests_user'), 'number_verification_requests', ['user'], unique=False)
    op.create_table('dest_groups',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('short_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('long_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('logo_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['logo_id'], ['blobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dest_groups_type'), 'dest_groups', ['type'], unique=False)
    op.create_table('destinations',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('country', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('sort_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('portrait_id', sa.Integer(), nullable=True),
    sa.Column('name_audio_id', sa.Integer(), nullable=True),
    sa.Column('base_endorsement', sa.Float(), server_default=sa.text('(0.5)'), nullable=False),
    sa.ForeignKeyConstraint(['name_audio_id'], ['blobs.id'], ),
    sa.ForeignKeyConstraint(['portrait_id'], ['blobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_destinations_base_endorsement'), 'destinations', ['base_endorsement'], unique=False)
    op.create_index(op.f('ix_destinations_country'), 'destinations', ['country'], unique=False)
    op.create_index(op.f('ix_destinations_sort_name'), 'destinations', ['sort_name'], unique=False)
    op.create_table('calls',
    sa.Column('id', sqlmodel.sql.sqltypes.GUID(), nullable=False),
    sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('provider_call_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=False),
    sa.Column('connected_at', sa.DateTime(), nullable=True),
    sa.Column('user_language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('destination_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['destination_id'], ['destinations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'provider_call_id', name='unique_call')
    )
    op.create_index(op.f('ix_calls_destination_id'), 'calls', ['destination_id'], unique=False)
    op.create_index(op.f('ix_calls_provider_call_id'), 'calls', ['provider_call_id'], unique=False)
    op.create_index(op.f('ix_calls_user_id'), 'calls', ['user_id'], unique=False)
    op.create_table('contacts',
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('contact', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('destination_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['destination_id'], ['destinations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contacts_destination_id'), 'contacts', ['destination_id'], unique=False)
    op.create_index(op.f('ix_contacts_group'), 'contacts', ['group'], unique=False)
    op.create_index(op.f('ix_contacts_type'), 'contacts', ['type'], unique=False)
    op.create_table('dest_group_link',
    sa.Column('destination_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('group_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['destination_id'], ['destinations.id'], ),
    sa.ForeignKeyConstraint(['group_id'], ['dest_groups.id'], ),
    sa.PrimaryKeyConstraint('destination_id', 'group_id')
    )
    op.create_table('dest_select_log',
    sa.Column('timestamp', sa.TIMESTAMP(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('event', sa.Enum('WEB_SUGGESTED', 'IVR_SUGGESTED', 'CALLING_USER', 'IN_MENU', 'CALLING_DESTINATION', 'DESTINATION_CONNECTED', 'FINISHED_SHORT_CALL', 'FINISHED_CALL', 'CALL_ABORTED', 'CALLING_USER_FAILED', 'CALLING_DESTINATION_FAILED', name='destinationselectionlogevent'), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('destination_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('call_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['destination_id'], ['destinations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dest_select_log_call_id'), 'dest_select_log', ['call_id'], unique=False)
    op.create_index(op.f('ix_dest_select_log_destination_id'), 'dest_select_log', ['destination_id'], unique=False)
    op.create_index(op.f('ix_dest_select_log_timestamp'), 'dest_select_log', ['timestamp'], unique=False)
    op.create_index(op.f('ix_dest_select_log_user_id'), 'dest_select_log', ['user_id'], unique=False)
    op.create_table('user_feedback',
    sa.Column('token', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('issued_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('feedback_entered_at', sa.DateTime(), nullable=True),
    sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('destination_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('calling_code', sa.Integer(), nullable=False),
    sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('convinced', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('technical_problems', sa.Boolean(), nullable=True),
    sa.Column('additional', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['destination_id'], ['destinations.id'], ),
    sa.PrimaryKeyConstraint('token')
    )
    op.create_index(op.f('ix_user_feedback_calling_code'), 'user_feedback', ['calling_code'], unique=False)
    op.create_index(op.f('ix_user_feedback_convinced'), 'user_feedback', ['convinced'], unique=False)
    op.create_index(op.f('ix_user_feedback_destination_id'), 'user_feedback', ['destination_id'], unique=False)
    op.create_index(op.f('ix_user_feedback_expires_at'), 'user_feedback', ['expires_at'], unique=False)
    op.create_index(op.f('ix_user_feedback_feedback_entered_at'), 'user_feedback', ['feedback_entered_at'], unique=False)
    op.create_index(op.f('ix_user_feedback_issued_at'), 'user_feedback', ['issued_at'], unique=False)
    op.create_index(op.f('ix_user_feedback_language'), 'user_feedback', ['language'], unique=False)
    op.create_index(op.f('ix_user_feedback_technical_problems'), 'user_feedback', ['technical_problems'], unique=False)
    op.create_index(op.f('ix_user_feedback_user_id'), 'user_feedback', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_user_feedback_user_id'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_technical_problems'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_language'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_issued_at'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_feedback_entered_at'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_expires_at'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_destination_id'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_convinced'), table_name='user_feedback')
    op.drop_index(op.f('ix_user_feedback_calling_code'), table_name='user_feedback')
    op.drop_table('user_feedback')
    op.drop_index(op.f('ix_dest_select_log_user_id'), table_name='dest_select_log')
    op.drop_index(op.f('ix_dest_select_log_timestamp'), table_name='dest_select_log')
    op.drop_index(op.f('ix_dest_select_log_destination_id'), table_name='dest_select_log')
    op.drop_index(op.f('ix_dest_select_log_call_id'), table_name='dest_select_log')
    op.drop_table('dest_select_log')
    op.drop_table('dest_group_link')
    op.drop_index(op.f('ix_contacts_type'), table_name='contacts')
    op.drop_index(op.f('ix_contacts_group'), table_name='contacts')
    op.drop_index(op.f('ix_contacts_destination_id'), table_name='contacts')
    op.drop_table('contacts')
    op.drop_index(op.f('ix_calls_user_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_provider_call_id'), table_name='calls')
    op.drop_index(op.f('ix_calls_destination_id'), table_name='calls')
    op.drop_table('calls')
    op.drop_index(op.f('ix_destinations_sort_name'), table_name='destinations')
    op.drop_index(op.f('ix_destinations_country'), table_name='destinations')
    op.drop_index(op.f('ix_destinations_base_endorsement'), table_name='destinations')
    op.drop_table('destinations')
    op.drop_index(op.f('ix_dest_groups_type'), table_name='dest_groups')
    op.drop_table('dest_groups')
    op.drop_index(op.f('ix_number_verification_requests_user'), table_name='number_verification_requests')
    op.drop_index(op.f('ix_number_verification_requests_requested_at'), table_name='number_verification_requests')
    op.drop_index(op.f('ix_number_verification_requests_completed_at'), table_name='number_verification_requests')
    op.drop_table('number_verification_requests')
    op.drop_index(op.f('ix_medialists_created_at'), table_name='medialists')
    op.drop_table('medialists')
    op.drop_index(op.f('ix_blobs_type'), table_name='blobs')
    op.drop_table('blobs')
    # ### end Alembic commands ###
