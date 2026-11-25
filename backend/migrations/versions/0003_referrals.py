"""Link qualifying participations to referrals and record failure reasons."""

import sqlalchemy as sa
from alembic import op

revision = "0003_referrals"
down_revision = "0002_surveys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("referrals") as batch:
        batch.add_column(sa.Column("participation_id", sa.Integer()))
        batch.add_column(sa.Column("failure_reason", sa.String(500)))
        batch.create_foreign_key(
            "fk_referrals_participation_id", "participations", ["participation_id"], ["id"]
        )
        batch.create_unique_constraint("uq_referrals_participation_id", ["participation_id"])


def downgrade() -> None:
    with op.batch_alter_table("referrals") as batch:
        batch.drop_constraint("uq_referrals_participation_id", type_="unique")
        batch.drop_constraint("fk_referrals_participation_id", type_="foreignkey")
        batch.drop_column("failure_reason")
        batch.drop_column("participation_id")
