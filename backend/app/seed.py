from datetime import date

from sqlalchemy import select

from .attribution import REFERRAL_SOURCE_NAME, ensure_personal_link, ensure_source
from .db import SessionLocal, lock_for_write
from .models import Interest, Member, MemberInterest, StaffAccount
from .security import hash_password, now_utc

DEMO_ADMIN_EMAIL = "admin@viewbox.test"
DEMO_ADMIN_PASSWORD = "ViewBoxDemo!32"
DEMO_MEMBER_PHONE = "+919876543210"


def seed() -> None:
    with SessionLocal() as db:
        lock_for_write(db)
        mumbai = ensure_source(db, "Mumbai WhatsApp", "mumbai-whatsapp")
        ensure_source(db, "Instagram", "instagram")
        ensure_source(db, "Website", "website")
        ensure_source(db, REFERRAL_SOURCE_NAME, "member-referral")

        if db.scalar(select(StaffAccount.id).where(StaffAccount.email == DEMO_ADMIN_EMAIL)) is None:
            db.add(StaffAccount(
                email=DEMO_ADMIN_EMAIL,
                password_hash=hash_password(DEMO_ADMIN_PASSWORD),
                role="admin",
            ))

        member = db.scalar(select(Member).where(Member.phone_e164 == DEMO_MEMBER_PHONE))
        if member is None:
            joined_at = now_utc()
            member = Member(
                phone_e164=DEMO_MEMBER_PHONE,
                name="Demo Member",
                date_of_birth=date(1994, 6, 15),
                gender="female",
                city="Mumbai",
                income_range="under_25000",
                source_id=mumbai.id,
                joined_at=joined_at,
                profile_completed_at=joined_at,
            )
            db.add(member)
            db.flush()
            for name in ("Food & beverages", "Shopping"):
                interest = db.scalar(select(Interest).where(Interest.name == name))
                if interest is None:
                    interest = Interest(name=name)
                    db.add(interest)
                    db.flush()
                db.add(MemberInterest(member_id=member.id, interest_id=interest.id))

        ensure_personal_link(db, member, "demo-member")
        db.commit()


if __name__ == "__main__":
    seed()
    print("ViewBox demo data is ready.")
