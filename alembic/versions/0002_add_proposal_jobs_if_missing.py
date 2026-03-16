"""Add proposal_jobs table if missing (e.g. DB was migrated before 0001 included it)."""

from alembic import op

revision = "0002_add_proposal_jobs_if_missing"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS proposal_jobs (
            id UUID NOT NULL,
            proposal_id UUID NOT NULL,
            action VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            payload JSONB NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            published_at TIMESTAMP WITH TIME ZONE,
            processed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            CONSTRAINT fk_proposal_jobs_proposal_id_proposals
                FOREIGN KEY (proposal_id) REFERENCES proposals (id) ON DELETE CASCADE
        )
    """)


def downgrade() -> None:
    op.drop_table("proposal_jobs", if_exists=True)
