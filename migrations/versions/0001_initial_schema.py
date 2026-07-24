"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-24

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('user_id',       sa.Integer(),     primary_key=True, autoincrement=True),
        sa.Column('matric_number', sa.String(20),    nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255),   nullable=False),
        sa.Column('full_name',     sa.String(100),   nullable=False),
        sa.Column('email',         sa.String(120),   nullable=True),
        sa.Column('photo_url',     sa.String(255),   nullable=True),
        sa.Column('role',          sa.String(20),    nullable=False, server_default='voter'),
        sa.Column('is_active',     sa.Boolean(),     nullable=False, server_default='1'),
        sa.Column('created_at',    sa.DateTime(),    nullable=True),
        if_not_exists=True,
    )
    op.create_index('ix_users_matric_number', 'users', ['matric_number'])
    op.create_index('ix_users_email',         'users', ['email'])

    op.create_table(
        'elections',
        sa.Column('election_id',    sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column('title',          sa.String(150), nullable=False),
        sa.Column('description',    sa.Text(),      nullable=True),
        sa.Column('status',         sa.String(20),  nullable=False, server_default='draft'),
        sa.Column('start_at',       sa.DateTime(),  nullable=False),
        sa.Column('end_at',         sa.DateTime(),  nullable=False),
        sa.Column('public_key_pem', sa.Text(),      nullable=False, server_default=''),
        sa.Column('created_by',     sa.Integer(),   sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('created_at',     sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_elections_status', 'elections', ['status'])

    op.create_table(
        'positions',
        sa.Column('position_id',   sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('election_id',   sa.Integer(),    sa.ForeignKey('elections.election_id'), nullable=False),
        sa.Column('title',         sa.String(100),  nullable=False),
        sa.Column('display_order', sa.Integer(),    server_default='0'),
    )

    op.create_table(
        'candidates',
        sa.Column('candidate_id',  sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('position_id',   sa.Integer(),    sa.ForeignKey('positions.position_id'), nullable=False),
        sa.Column('full_name',     sa.String(100),  nullable=False),
        sa.Column('matric_number', sa.String(20),   nullable=True),
        sa.Column('photo_url',     sa.String(255),  nullable=True),
        sa.Column('manifesto',     sa.Text(),        nullable=True),
    )

    op.create_table(
        'eligible_voters',
        sa.Column('eligibility_id', sa.Integer(),   primary_key=True, autoincrement=True),
        sa.Column('election_id',    sa.Integer(),   sa.ForeignKey('elections.election_id'), nullable=False),
        sa.Column('matric_number',  sa.String(20),  nullable=False),
        sa.Column('has_voted',      sa.Boolean(),   nullable=False, server_default='0'),
        sa.UniqueConstraint('election_id', 'matric_number', name='uq_election_voter'),
    )
    op.create_index('ix_eligible_voters_matric_number', 'eligible_voters', ['matric_number'])

    op.create_table(
        'ballots',
        sa.Column('ballot_id',              sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('election_id',            sa.Integer(),    sa.ForeignKey('elections.election_id'), nullable=False),
        sa.Column('anonymised_voter_ref',   sa.String(64),   nullable=False),
        sa.Column('encrypted_vote_data',    sa.Text(),        nullable=False),
        sa.Column('ballot_hash_sha256',     sa.String(64),   nullable=False, unique=True),
        sa.Column('receipt_id',             sa.String(40),   nullable=False, unique=True),
        sa.Column('submitted_at',           sa.DateTime(),   nullable=True),
        sa.Column('integrity_verified',     sa.Boolean(),    nullable=True),
    )
    op.create_index('ix_ballots_anonymised_voter_ref', 'ballots', ['anonymised_voter_ref'])

    op.create_table(
        'audit_log',
        sa.Column('log_id',            sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('user_id',           sa.Integer(),    sa.ForeignKey('users.user_id'), nullable=True),
        sa.Column('action_performed',  sa.String(255),  nullable=False),
        sa.Column('ip_address',        sa.String(45),   nullable=False),
        sa.Column('metadata_json',     sa.Text(),        nullable=True),
        sa.Column('timestamp',         sa.DateTime(),   nullable=True),
    )
    op.create_index('ix_audit_log_action_performed', 'audit_log', ['action_performed'])
    op.create_index('ix_audit_log_timestamp',        'audit_log', ['timestamp'])

    op.create_table(
        'password_reset_tokens',
        sa.Column('token_id',    sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column('user_id',     sa.Integer(),    sa.ForeignKey('users.user_id'), nullable=False),
        sa.Column('token_hash',  sa.String(64),   nullable=False, unique=True),
        sa.Column('expires_at',  sa.DateTime(),   nullable=False),
        sa.Column('used',        sa.Boolean(),    nullable=False, server_default='0'),
        sa.Column('created_at',  sa.DateTime(),   nullable=True),
    )
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'])


def downgrade():
    op.drop_table('password_reset_tokens')
    op.drop_table('audit_log')
    op.drop_table('ballots')
    op.drop_table('eligible_voters')
    op.drop_table('candidates')
    op.drop_table('positions')
    op.drop_table('elections')
    op.drop_table('users')
