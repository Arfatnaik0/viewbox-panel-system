"""Create the initial signup, attribution, profile and login tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_signup"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100, collation="NOCASE"), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone_e164", sa.String(16), nullable=False, unique=True),
        sa.Column("name", sa.String(120)),
        sa.Column("email", sa.String(254)),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("gender", sa.String(60)),
        sa.Column("city", sa.String(100)),
        sa.Column("income_range", sa.String(100)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("signup_link_id", sa.Integer(), sa.ForeignKey("signup_links.id", name="fk_members_signup_link_id")),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.Column("profile_completed_at", sa.DateTime()),
        sa.Column("imported_last_completed_on", sa.Date()),
    )
    op.create_index("ix_members_source_id", "members", ["source_id"])
    op.create_table(
        "signup_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("owner_member_id", sa.Integer(), sa.ForeignKey("members.id"), unique=True),
        sa.Column("token", sa.String(80), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "uq_signup_links_active_admin_source",
        "signup_links",
        ["source_id"],
        unique=True,
        sqlite_where=sa.text("owner_member_id IS NULL AND active = 1"),
    )
    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referred_member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False, unique=True),
        sa.Column("referrer_member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("claimed_name", sa.String(120)),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(20)),
        sa.CheckConstraint(
            "referrer_member_id IS NULL OR referrer_member_id != referred_member_id",
            name="ck_referrals_distinct_members",
        ),
    )
    op.create_index("ix_referrals_referrer_member_id", "referrals", ["referrer_member_id"])
    op.create_table(
        "interests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80, collation="NOCASE"), nullable=False, unique=True),
    )
    op.create_table(
        "member_interests",
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), primary_key=True),
        sa.Column("interest_id", sa.Integer(), sa.ForeignKey("interests.id"), primary_key=True),
    )
    op.create_table(
        "staff_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(254, collation="NOCASE"), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
    )
    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("phone_e164", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime()),
    )
    op.create_index("ix_otp_challenges_phone_e164", "otp_challenges", ["phone_e164"])
    op.create_table(
        "login_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id")),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staff_accounts.id")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(member_id IS NOT NULL AND staff_id IS NULL)"
            " OR (member_id IS NULL AND staff_id IS NOT NULL)",
            name="ck_login_sessions_exactly_one_owner",
        ),
    )
    op.create_index("ix_login_sessions_member_id", "login_sessions", ["member_id"])
    op.create_index("ix_login_sessions_staff_id", "login_sessions", ["staff_id"])


def downgrade() -> None:
    op.drop_table("login_sessions")
    op.drop_table("otp_challenges")
    op.drop_table("staff_accounts")
    op.drop_table("member_interests")
    op.drop_table("interests")
    op.drop_table("referrals")
    op.execute("UPDATE members SET signup_link_id = NULL")
    op.drop_table("signup_links")
    op.drop_table("members")
    op.drop_table("sources")
