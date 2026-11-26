"""Keep legacy member IDs so CSV referrals can be resolved on later imports."""

import sqlalchemy as sa
from alembic import op

revision = "0004_csv_import"
down_revision = "0003_referrals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_member_keys",
        sa.Column("legacy_id", sa.String(120), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id")),
    )


def downgrade() -> None:
    op.drop_table("legacy_member_keys")
