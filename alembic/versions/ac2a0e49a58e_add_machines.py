"""Add machines

Revision ID: ac2a0e49a58e
Revises: c67f421bc237
Create Date: 2022-09-20 19:01:21.727279

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = 'ac2a0e49a58e'
down_revision = 'c67f421bc237'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('machines',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('hostname', sa.Text(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('hostname')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('machines')
    # ### end Alembic commands ###