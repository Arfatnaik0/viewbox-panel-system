from secrets import token_urlsafe

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Member, Referral, SignupLink, Source
from .schemas import OtpVerify
from .security import api_error, now_utc

REFERRAL_SOURCE_NAME = "Member Referral"


def active_link(db: Session, token: str) -> tuple[SignupLink, Source] | None:
    row = db.execute(
        select(SignupLink, Source)
        .join(Source, Source.id == SignupLink.source_id)
        .where(SignupLink.token == token, SignupLink.active.is_(True), Source.active.is_(True))
    ).one_or_none()
    if row is None:
        return None
    link, source = row
    return link, source


def ensure_source(db: Session, name: str, token: str | None = None) -> Source:
    source = db.scalar(select(Source).where(Source.name == name))
    if source is None:
        source = Source(name=name)
        db.add(source)
        db.flush()
    admin_link = db.scalar(
        select(SignupLink).where(
            SignupLink.source_id == source.id,
            SignupLink.owner_member_id.is_(None),
            SignupLink.active.is_(True),
        )
    )
    if admin_link is None:
        db.add(SignupLink(source_id=source.id, token=token or token_urlsafe(12)))
    return source


def ensure_personal_link(db: Session, member: Member, token: str | None = None) -> SignupLink:
    link = db.scalar(select(SignupLink).where(SignupLink.owner_member_id == member.id))
    if link is None:
        source = ensure_source(db, REFERRAL_SOURCE_NAME, "member-referral")
        link = SignupLink(
            source_id=source.id, owner_member_id=member.id, token=token or token_urlsafe(12)
        )
        db.add(link)
    return link


def signup_member(db: Session, phone: str, data: OtpVerify) -> Member:
    link = None
    if data.source_token is not None:
        match = active_link(db, data.source_token)
        if match is None:
            raise api_error(422, "invalid_source_link", "This signup link is no longer available.")
        link, source = match
    elif data.source_id is not None:
        source = db.get(Source, data.source_id)
        if source is None or not source.active:
            raise api_error(422, "invalid_source", "Choose an available signup source.")
    else:
        raise api_error(422, "source_required", "How did you hear about ViewBox?")

    member = Member(
        phone_e164=phone,
        source_id=source.id,
        signup_link_id=link.id if link else None,
        joined_at=now_utc(),
    )
    db.add(member)
    db.flush()

    referrer_id = link.owner_member_id if link else None
    if referrer_id is not None:
        db.add(Referral(
            referred_member_id=member.id,
            referrer_member_id=referrer_id,
            verification_status="verified",
            stage="lead",
        ))
    elif data.referrer_name is not None:
        db.add(Referral(
            referred_member_id=member.id,
            claimed_name=data.referrer_name,
            verification_status="pending",
        ))
    return member
