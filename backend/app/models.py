from datetime import date, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100, collation="NOCASE"), unique=True)
    active: Mapped[bool] = mapped_column(default=True)


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    phone_e164: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(254))
    date_of_birth: Mapped[date | None]
    gender: Mapped[str | None] = mapped_column(String(60))
    city: Mapped[str | None] = mapped_column(String(100))
    income_range: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    signup_link_id: Mapped[int | None] = mapped_column(
        ForeignKey("signup_links.id", name="fk_members_signup_link_id", use_alter=True)
    )
    joined_at: Mapped[datetime]
    profile_completed_at: Mapped[datetime | None]
    imported_last_completed_on: Mapped[date | None]


class SignupLink(Base):
    __tablename__ = "signup_links"
    __table_args__ = (
        Index(
            "uq_signup_links_active_admin_source",
            "source_id",
            unique=True,
            sqlite_where=text("owner_member_id IS NULL AND active = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    owner_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), unique=True)
    token: Mapped[str] = mapped_column(String(80), unique=True)
    active: Mapped[bool] = mapped_column(default=True)


class Referral(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        CheckConstraint(
            "referrer_member_id IS NULL OR referrer_member_id != referred_member_id",
            name="ck_referrals_distinct_members",
        ),
        UniqueConstraint("participation_id", name="uq_referrals_participation_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    referred_member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), unique=True)
    referrer_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    claimed_name: Mapped[str | None] = mapped_column(String(120))
    verification_status: Mapped[str] = mapped_column(String(20))
    stage: Mapped[str | None] = mapped_column(String(20))
    participation_id: Mapped[int | None] = mapped_column(
        ForeignKey("participations.id", name="fk_referrals_participation_id")
    )
    failure_reason: Mapped[str | None] = mapped_column(String(500))


class Interest(Base):
    __tablename__ = "interests"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80, collation="NOCASE"), unique=True)


class MemberInterest(Base):
    __tablename__ = "member_interests"

    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), primary_key=True)
    interest_id: Mapped[int] = mapped_column(ForeignKey("interests.id"), primary_key=True)


class StaffAccount(Base):
    __tablename__ = "staff_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254, collation="NOCASE"), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(20), default="admin")


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    phone_e164: Mapped[str] = mapped_column(String(16), index=True)
    expires_at: Mapped[datetime]
    failed_attempts: Mapped[int] = mapped_column(default=0)
    consumed_at: Mapped[datetime | None]


class LoginSession(Base):
    __tablename__ = "login_sessions"
    __table_args__ = (
        CheckConstraint(
            "(member_id IS NOT NULL AND staff_id IS NULL)"
            " OR (member_id IS NULL AND staff_id IS NOT NULL)",
            name="ck_login_sessions_exactly_one_owner",
        ),
    )

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_accounts.id"), index=True)
    expires_at: Mapped[datetime]
