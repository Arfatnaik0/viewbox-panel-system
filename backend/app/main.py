import hmac
from datetime import timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, FastAPI, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from .attribution import active_link, ensure_personal_link, ensure_source, signup_member
from .csv_import import router as csv_import_router
from .db import SessionLocal, lock_for_write, make_engine
from .dependencies import (
    STAFF_ROLES,
    AdminToken,
    CurrentAdmin,
    CurrentMember,
    CurrentStaff,
    Database,
    MemberToken,
)
from .meta_leads import router as meta_leads_router
from .models import (
    Interest,
    LoginSession,
    Member,
    MemberInterest,
    OtpChallenge,
    SignupLink,
    Source,
    StaffAccount,
)
from .operations import router as operations_router
from .schemas import (
    AdminLogin,
    AdminSource,
    AdminSummary,
    MemberSummary,
    OtpIssued,
    OtpRequest,
    OtpVerify,
    ProfileUpdate,
    SignupLinkSummary,
    SourceCreate,
    SourceSummary,
    StaffSession,
)
from .security import (
    ADMIN_COOKIE,
    DEMO_OTP,
    MEMBER_COOKIE,
    OTP_MAX_ATTEMPTS,
    api_error,
    hash_token,
    now_utc,
    password_matches,
    set_session_cookie,
)
from .surveys import router as surveys_router

OTP_TTL = timedelta(minutes=5)
MEMBER_SESSION_SECONDS = 24 * 60 * 60
ADMIN_SESSION_SECONDS = 12 * 60 * 60
DUMMY_PASSWORD_HASH = "0" * 32 + "$" + "0" * 128

router = APIRouter(prefix="/api")


def member_summary(db: Session, member: Member) -> MemberSummary:
    source = db.get(Source, member.source_id)
    link = db.scalar(select(SignupLink).where(SignupLink.owner_member_id == member.id))
    interests = db.scalars(
        select(Interest.name)
        .join(MemberInterest, MemberInterest.interest_id == Interest.id)
        .where(MemberInterest.member_id == member.id)
        .order_by(Interest.name)
    ).all()
    return MemberSummary(
        id=member.id,
        phone=member.phone_e164,
        name=member.name,
        date_of_birth=member.date_of_birth,
        gender=member.gender,
        city=member.city,
        income_range=member.income_range,
        interests=list(interests),
        profile_complete=member.profile_completed_at is not None,
        source=SourceSummary(id=source.id, name=source.name),
        referral_token=link.token,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/signup/sources")
def signup_sources(db: Database) -> list[SourceSummary]:
    sources = db.scalars(select(Source).where(Source.active.is_(True)).order_by(Source.name))
    return [SourceSummary(id=source.id, name=source.name) for source in sources]


@router.get("/signup/links/{token}")
def signup_link(token: str, db: Database) -> SignupLinkSummary:
    match = active_link(db, token)
    if match is None:
        raise api_error(404, "invalid_source_link", "This signup link is no longer available.")
    link, source = match
    return SignupLinkSummary(
        source=SourceSummary(id=source.id, name=source.name),
        personal=link.owner_member_id is not None,
    )


@router.post("/auth/otp/request")
def request_otp(data: OtpRequest, db: Database) -> OtpIssued:
    challenge = OtpChallenge(
        id=token_urlsafe(24), phone_e164=data.phone, expires_at=now_utc() + OTP_TTL
    )
    db.add(challenge)
    db.commit()
    return OtpIssued(challenge_id=challenge.id, demo_code=DEMO_OTP)


@router.post("/auth/otp/verify")
def verify_otp(
    data: OtpVerify, db: Database, response: Response, token: MemberToken = None
) -> MemberSummary:
    lock_for_write(db)
    challenge = db.get(OtpChallenge, data.challenge_id)
    time = now_utc()
    if challenge is None or challenge.consumed_at is not None or challenge.expires_at <= time:
        raise api_error(401, "otp_expired", "This code has expired or was already used. Request a new code.")
    if challenge.failed_attempts >= OTP_MAX_ATTEMPTS:
        raise api_error(429, "otp_attempts_exhausted", "Too many attempts. Request a new code.")
    if not hmac.compare_digest(data.code.encode(), DEMO_OTP.encode()):
        challenge.failed_attempts += 1
        db.commit()
        raise api_error(401, "invalid_otp", "That code is incorrect.")

    member = db.scalar(select(Member).where(Member.phone_e164 == challenge.phone_e164))
    if member is None:
        member = signup_member(db, challenge.phone_e164, data)
    if member.status != "active":
        raise api_error(403, "member_inactive", "This member account is inactive.")

    ensure_personal_link(db, member)
    challenge.consumed_at = time
    if token:
        db.execute(delete(LoginSession).where(
            LoginSession.token_hash == hash_token(token), LoginSession.member_id.is_not(None)
        ))
    new_token = token_urlsafe(32)
    db.add(LoginSession(
        token_hash=hash_token(new_token),
        member_id=member.id,
        expires_at=time + timedelta(seconds=MEMBER_SESSION_SECONDS),
    ))
    db.commit()
    set_session_cookie(response, MEMBER_COOKIE, new_token, MEMBER_SESSION_SECONDS)
    return member_summary(db, member)


@router.get("/member/me")
def member_me(db: Database, member: CurrentMember) -> MemberSummary:
    return member_summary(db, member)


@router.put("/member/profile")
def update_profile(data: ProfileUpdate, db: Database, member: CurrentMember) -> MemberSummary:
    lock_for_write(db)
    member.name = data.name
    member.date_of_birth = data.date_of_birth
    member.gender = data.gender
    member.city = data.city
    member.income_range = data.income_range
    if member.profile_completed_at is None:
        member.profile_completed_at = now_utc()

    db.execute(delete(MemberInterest).where(MemberInterest.member_id == member.id))
    for name in data.interests:
        interest = db.scalar(select(Interest).where(Interest.name == name))
        if interest is None:
            interest = Interest(name=name)
            db.add(interest)
            db.flush()
        db.add(MemberInterest(member_id=member.id, interest_id=interest.id))
    db.commit()
    return member_summary(db, member)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(db: Database, member_token: MemberToken = None, admin_token: AdminToken = None) -> Response:
    hashes = [hash_token(token) for token in (member_token, admin_token) if token]
    if hashes:
        db.execute(delete(LoginSession).where(LoginSession.token_hash.in_(hashes)))
        db.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    for cookie in (MEMBER_COOKIE, ADMIN_COOKIE):
        response.delete_cookie(cookie, path="/api")
    return response


@router.post("/admin/login")
def admin_login(
    data: AdminLogin, db: Database, response: Response, token: AdminToken = None
) -> AdminSummary:
    staff = db.scalar(select(StaffAccount).where(StaffAccount.email == data.email))
    matches = password_matches(data.password, staff.password_hash if staff else DUMMY_PASSWORD_HASH)
    if not matches or staff is None or staff.role not in STAFF_ROLES:
        raise api_error(401, "invalid_admin_login", "The email or password is incorrect.")

    if token:
        db.execute(delete(LoginSession).where(
            LoginSession.token_hash == hash_token(token), LoginSession.staff_id.is_not(None)
        ))
    new_token = token_urlsafe(32)
    db.add(LoginSession(
        token_hash=hash_token(new_token),
        staff_id=staff.id,
        expires_at=now_utc() + timedelta(seconds=ADMIN_SESSION_SECONDS),
    ))
    db.commit()
    set_session_cookie(response, ADMIN_COOKIE, new_token, ADMIN_SESSION_SECONDS)
    return AdminSummary(email=staff.email)


@router.get("/admin/me")
def admin_me(admin: CurrentAdmin) -> AdminSummary:
    return AdminSummary(email=admin.email)


@router.get("/admin/session")
def staff_session(staff: CurrentStaff) -> StaffSession:
    return StaffSession(email=staff.email, role=staff.role)


@router.get("/admin/sources")
def admin_sources(db: Database, _admin: CurrentAdmin) -> list[AdminSource]:
    rows = db.execute(
        select(Source, SignupLink)
        .join(SignupLink, SignupLink.source_id == Source.id)
        .where(
            Source.active.is_(True),
            SignupLink.active.is_(True),
            SignupLink.owner_member_id.is_(None),
        )
        .order_by(Source.name)
    )
    return [AdminSource(id=source.id, name=source.name, token=link.token) for source, link in rows]


@router.post("/admin/sources", status_code=status.HTTP_201_CREATED)
def create_source(data: SourceCreate, db: Database, _admin: CurrentAdmin) -> AdminSource:
    lock_for_write(db)
    if db.scalar(select(Source.id).where(Source.name == data.name)) is not None:
        raise api_error(409, "source_exists", "A source with this name already exists.")
    source = ensure_source(db, data.name)
    db.commit()
    link = db.scalar(select(SignupLink).where(SignupLink.source_id == source.id))
    return AdminSource(id=source.id, name=source.name, token=link.token)


def create_app(database_url: str | None = None) -> FastAPI:
    application = FastAPI(title="ViewBox API")
    application.state.session_factory = (
        sessionmaker(make_engine(database_url), expire_on_commit=False)
        if database_url is not None else SessionLocal
    )

    @application.middleware("http")
    async def disable_api_caching(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    application.include_router(router)
    application.include_router(surveys_router)
    application.include_router(operations_router)
    application.include_router(csv_import_router)
    application.include_router(meta_leads_router)
    return application


app = create_app()
