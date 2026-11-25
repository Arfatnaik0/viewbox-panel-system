"""Create surveys, targeting rules, interests and applications."""

import sqlalchemy as sa
from alembic import op

revision = "0002_surveys"
down_revision = "0001_signup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "surveys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quota", sa.Integer(), nullable=False),
        sa.Column("opens_at", sa.DateTime(), nullable=False),
        sa.Column("closes_at", sa.DateTime(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.CheckConstraint("quota > 0", name="ck_surveys_positive_quota"),
        sa.CheckConstraint("opens_at < closes_at", name="ck_surveys_dates_in_order"),
    )
    op.create_table(
        "survey_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id"), nullable=False),
        sa.Column("field", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("allowed_values", sa.JSON(), nullable=False),
        sa.UniqueConstraint("survey_id", "field", name="uq_survey_rules_survey_field"),
        sa.CheckConstraint(
            "field IN ('age', 'city', 'gender', 'income_range')", name="ck_survey_rules_known_field"
        ),
        sa.CheckConstraint("mode IN ('strict', 'flexible')", name="ck_survey_rules_known_mode"),
    )
    op.create_table(
        "survey_interests",
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id"), primary_key=True),
        sa.Column("interest_id", sa.Integer(), sa.ForeignKey("interests.id"), primary_key=True),
    )
    op.create_table(
        "participations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("survey_id", sa.Integer(), sa.ForeignKey("surveys.id"), nullable=False),
        sa.Column("eligibility_status", sa.String(10), nullable=False),
        sa.Column("eligibility_reason", sa.Text(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.Column("fit_at", sa.DateTime()),
        sa.Column("fit_by_id", sa.Integer(), sa.ForeignKey("staff_accounts.id")),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("completed_by_id", sa.Integer(), sa.ForeignKey("staff_accounts.id")),
        sa.UniqueConstraint("member_id", "survey_id", name="uq_participations_member_survey"),
        sa.CheckConstraint(
            "eligibility_status IN ('approved', 'waitlisted')", name="ck_participations_saved_status"
        ),
    )
    op.create_index(
        "ix_participations_survey_status", "participations", ["survey_id", "eligibility_status"]
    )


def downgrade() -> None:
    op.drop_table("participations")
    op.drop_table("survey_interests")
    op.drop_table("survey_rules")
    op.drop_table("surveys")
