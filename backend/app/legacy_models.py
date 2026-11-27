from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class LegacyMemberKey(Base):
    __tablename__ = "legacy_member_keys"

    legacy_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    # A null target records an ID that was observed on distinct members.
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))


class LegacyReferralKey(Base):
    """The legacy IDs used to verify a referral during CSV import."""

    __tablename__ = "legacy_referral_keys"

    referral_id: Mapped[int] = mapped_column(ForeignKey("referrals.id"), primary_key=True)
    legacy_id: Mapped[str] = mapped_column(ForeignKey("legacy_member_keys.legacy_id"), primary_key=True, index=True)
