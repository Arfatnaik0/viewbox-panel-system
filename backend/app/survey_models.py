from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .models import Interest


class Survey(Base):
    __tablename__ = "surveys"
    __table_args__ = (
        CheckConstraint("quota > 0", name="ck_surveys_positive_quota"),
        CheckConstraint("opens_at < closes_at", name="ck_surveys_dates_in_order"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    quota: Mapped[int]
    opens_at: Mapped[datetime]
    closes_at: Mapped[datetime]
    published: Mapped[bool] = mapped_column(default=False)
    rules: Mapped[list[SurveyRule]] = relationship(order_by="SurveyRule.id", cascade="all, delete-orphan")
    interests: Mapped[list[Interest]] = relationship(secondary="survey_interests", order_by=Interest.name)


class SurveyRule(Base):
    __tablename__ = "survey_rules"
    __table_args__ = (
        UniqueConstraint("survey_id", "field", name="uq_survey_rules_survey_field"),
        CheckConstraint(
            "field IN ('age', 'city', 'gender', 'income_range')", name="ck_survey_rules_known_field"
        ),
        CheckConstraint("mode IN ('strict', 'flexible')", name="ck_survey_rules_known_mode"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"))
    field: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(10))
    allowed_values: Mapped[list[int | str]] = mapped_column(JSON)


class SurveyInterest(Base):
    __tablename__ = "survey_interests"

    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"), primary_key=True)
    interest_id: Mapped[int] = mapped_column(ForeignKey("interests.id"), primary_key=True)


class Participation(Base):
    __tablename__ = "participations"
    __table_args__ = (
        UniqueConstraint("member_id", "survey_id", name="uq_participations_member_survey"),
        CheckConstraint(
            "eligibility_status IN ('approved', 'waitlisted')", name="ck_participations_saved_status"
        ),
        Index("ix_participations_survey_status", "survey_id", "eligibility_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    survey_id: Mapped[int] = mapped_column(ForeignKey("surveys.id"))
    eligibility_status: Mapped[str] = mapped_column(String(10))
    eligibility_reason: Mapped[str] = mapped_column(Text)
    applied_at: Mapped[datetime]
    fit_at: Mapped[datetime | None]
    fit_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_accounts.id"))
    completed_at: Mapped[datetime | None]
    completed_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff_accounts.id"))
