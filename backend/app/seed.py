from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .attribution import REFERRAL_SOURCE_NAME, ensure_personal_link, ensure_source
from .db import SessionLocal, lock_for_write
from .models import Interest, Member, MemberInterest, Referral, Source, StaffAccount
from .security import hash_password, now_utc
from .survey_models import Survey, SurveyInterest, SurveyRule

DEMO_ADMIN_EMAIL = "admin@viewbox.test"
DEMO_ADMIN_PASSWORD = "ViewBoxDemo!32"
DEMO_MEMBER_PHONE = "+919876543210"
DEMO_STAFF_EMAIL = "staff@viewbox.test"
DEMO_STAFF_PASSWORD = "ViewBoxStaff!32"
DEMO_REFERRED_PHONE = "+919876543299"


def seed_account(db: Session, email: str, password: str, role: str) -> None:
    if db.scalar(select(StaffAccount.id).where(StaffAccount.email == email)) is None:
        db.add(StaffAccount(email=email, password_hash=hash_password(password), role=role))


def seed_interest(db: Session, name: str) -> Interest:
    interest = db.scalar(select(Interest).where(Interest.name == name))
    if interest is None:
        interest = Interest(name=name)
        db.add(interest)
        db.flush()
    return interest


def seed_member(
    db: Session, phone: str, name: str, source: Source, signup_link_id: int | None = None,
) -> tuple[Member, bool]:
    member = db.scalar(select(Member).where(Member.phone_e164 == phone))
    if member is not None:
        return member, False

    joined_at = now_utc()
    member = Member(
        phone_e164=phone,
        name=name,
        date_of_birth=date(1994, 6, 15),
        gender="female",
        city="Mumbai",
        income_range="under_25000",
        source_id=source.id,
        signup_link_id=signup_link_id,
        joined_at=joined_at,
        profile_completed_at=joined_at,
    )
    db.add(member)
    db.flush()
    for interest_name in ("Food & beverages", "Shopping"):
        interest = seed_interest(db, interest_name)
        db.add(MemberInterest(member_id=member.id, interest_id=interest.id))
    return member, True


def seed_survey(
    db: Session, title: str, description: str, interest: str, city: str, mode: str,
) -> None:
    if db.scalar(select(Survey.id).where(Survey.title == title)) is not None:
        return

    now = now_utc()
    survey = Survey(
        title=title,
        description=description,
        opens_at=now - timedelta(days=1),
        closes_at=now + timedelta(days=13),
        quota=20,
        published=True,
    )
    db.add(survey)
    db.flush()
    db.add(SurveyInterest(survey_id=survey.id, interest_id=seed_interest(db, interest).id))
    db.add(SurveyRule(survey_id=survey.id, field="city", mode=mode, allowed_values=[city]))


def seed() -> None:
    with SessionLocal() as db:
        lock_for_write(db)
        mumbai = ensure_source(db, "Mumbai WhatsApp", "mumbai-whatsapp")
        ensure_source(db, "Instagram", "instagram")
        ensure_source(db, "Website", "website")
        referral_source = ensure_source(db, REFERRAL_SOURCE_NAME, "member-referral")
        seed_account(db, DEMO_ADMIN_EMAIL, DEMO_ADMIN_PASSWORD, "admin")
        seed_account(db, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD, "staff")

        member, _ = seed_member(db, DEMO_MEMBER_PHONE, "Demo Member", mumbai)
        referral_link = ensure_personal_link(db, member, "demo-member")
        db.flush()
        referred, created = seed_member(
            db, DEMO_REFERRED_PHONE, "Referred Demo Member", referral_source, referral_link.id,
        )
        ensure_personal_link(db, referred, "referred-demo-member")
        if created:
            db.add(Referral(
                referred_member_id=referred.id,
                referrer_member_id=member.id,
                verification_status="verified",
                stage="lead",
            ))

        seed_survey(
            db, "Everyday shopping in Mumbai", "Tell us where and how you shop for household items.",
            "Shopping", "Mumbai", "strict",
        )
        seed_survey(
            db, "Food delivery habits", "Share how you order food and what goes into your choices.",
            "Food & beverages", "Pune", "flexible",
        )
        db.commit()


if __name__ == "__main__":
    seed()
    print("ViewBox demo data is ready.")
