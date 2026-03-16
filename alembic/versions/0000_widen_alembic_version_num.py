"""Widen alembic_version.version_num so long revision IDs (e.g. 0002_add_proposal_jobs_if_missing) fit.

Runs first on fresh DBs; avoids manual ALTER on PostgreSQL when revision IDs exceed default length.
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
