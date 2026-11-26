"""Store Meta lead deliveries and their original member association."""

import sqlalchemy as sa
from alembic import op

revision = "0005_meta_leads"
down_revision = "0004_csv_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meta_leads",
        sa.Column("lead_id", sa.String(160), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("form_id", sa.String(160), nullable=False),
        sa.Column("campaign_id", sa.String(160), nullable=False),
        sa.Column("ad_id", sa.String(160)),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("created_member", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_meta_leads_member_id", "meta_leads", ["member_id"])


def downgrade() -> None:
    op.drop_table("meta_leads")
