from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '872bc9d0a203'
down_revision: Union[str, None] = 'd1c59573251f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

subscriptionstatus_enum = postgresql.ENUM(
    'active', 'past_due', 'canceled', 'incomplete', 'trialing',
    name='subscriptionstatus'
)


def upgrade() -> None:
    subscriptionstatus_enum.create(op.get_bind(), checkfirst=True)

    op.add_column('subscriptions', sa.Column('stripe_customer_id', sa.String(), nullable=True))
    op.add_column('subscriptions', sa.Column('stripe_subscription_id', sa.String(), nullable=True))
    op.add_column('subscriptions', sa.Column(
        'status',
        subscriptionstatus_enum,
        nullable=False,
        server_default='active',
    ))
    op.add_column('subscriptions', sa.Column('current_period_end', postgresql.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column(
        'cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()
    ))


def downgrade() -> None:
    op.drop_column('subscriptions', 'cancel_at_period_end')
    op.drop_column('subscriptions', 'current_period_end')
    op.drop_column('subscriptions', 'status')
    op.drop_column('subscriptions', 'stripe_subscription_id')
    op.drop_column('subscriptions', 'stripe_customer_id')

    subscriptionstatus_enum.drop(op.get_bind(), checkfirst=True)