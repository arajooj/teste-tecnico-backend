"""Widen alembic_version.version_num so long revision IDs fit.

Runs first on fresh DBs and avoids manual ALTER on PostgreSQL when
revision IDs exceed the default length.
"""

from alembic import op

revision = "0000_widen_version_num"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32)"
    )
