"""Track which legacy IDs were used to verify imported referrals."""

import sqlalchemy as sa
from alembic import op

revision = "0006_legacy_referral_keys"
down_revision = "0005_meta_leads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legacy_referral_keys",
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id"), primary_key=True),
        sa.Column("legacy_id", sa.String(120), sa.ForeignKey("legacy_member_keys.legacy_id"), primary_key=True),
    )
    op.create_index("ix_legacy_referral_keys_legacy_id", "legacy_referral_keys", ["legacy_id"])


def downgrade() -> None:
    op.drop_table("legacy_referral_keys")
