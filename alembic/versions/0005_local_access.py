"""Replace the legacy free label with local full access.

Revision ID: 0005_local_access
Revises: 0004_mature_content_controls
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_local_access"
down_revision: str | None = "0004_mature_content_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE subscriptions SET plan = 'local' WHERE plan = 'free'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE subscriptions SET plan = 'free' WHERE plan = 'local'"))
