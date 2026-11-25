import csv
from datetime import UTC, datetime
from io import StringIO
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import String, case, cast, distinct, func, or_, select
from sqlalchemy.orm import Session, aliased

from .db import lock_for_write
from .dependencies import CurrentMember, CurrentStaff, Database
from .models import Member, Referral, Source
from .schemas import SourceSummary
from .security import api_error, now_utc
from .survey_models import Participation, Survey


router = APIRouter(prefix="/api", tags=["operations"])
Referrer = aliased(Member)


class RespondentQuery(BaseModel):
    search: str = Field(default="", max_length=120)
    source_id: int | None = Field(default=None, gt=0)
    city: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=20)


class StaffReferrer(BaseModel):
    id: int
    name: str | None


class StaffReferral(BaseModel):
    id: int
    stage: str | None
    verification_status: str
    claimed_name: str | None
    referrer: StaffReferrer | None
    failure_reason: str | None


class Respondent(BaseModel):
    id: int
    name: str | None
    phone: str
    city: str | None
    source: SourceSummary
    status: str
    profile_complete: bool
    referral: StaffReferral | None


class RespondentFilters(BaseModel):
    sources: list[SourceSummary]
    cities: list[str]
    statuses: list[str]


class RespondentGrid(BaseModel):
    respondents: list[Respondent]
    filters: RespondentFilters


class StaffParticipation(BaseModel):
    id: int
    survey_id: int
    survey_title: str
    eligibility_status: str
    fit_at: datetime | None
    completed_at: datetime | None


class RespondentDetail(Respondent):
    participations: list[StaffParticipation]


class SourceStats(SourceSummary):
    signups: int
    fit: int
    completed: int


class MemberReferral(BaseModel):
    id: int
    name: str | None
    phone_masked: str
    stage: str
    failure_reason: str | None


FailureReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class ReferralReview(BaseModel):
    referrer_member_id: int | None = Field(default=None, gt=0)
    failure_reason: FailureReason | None = None

    @model_validator(mode="after")
    def require_one_decision(self):
        if (self.referrer_member_id is None) == (self.failure_reason is None):
            raise ValueError("Provide either the referrer’s member ID or a reason to reject the claim.")
        return self


class ReferralFailure(BaseModel):
    reason: FailureReason


def respondent_query():
    return (
        select(Member, Source, Referral, Referrer)
        .select_from(Member)
        .join(Source, Source.id == Member.source_id)
        .outerjoin(Referral, Referral.referred_member_id == Member.id)
        .outerjoin(Referrer, Referrer.id == Referral.referrer_member_id)
    )


def matching_respondents(db: Session, filters: RespondentQuery) -> list[Respondent]:
    query = respondent_query().order_by(Member.id.desc())
    search = filters.search.strip()
    if search:
        query = query.where(or_(
            cast(Member.id, String).contains(search, autoescape=True),
            Member.name.icontains(search, autoescape=True),
            Member.city.icontains(search, autoescape=True),
        ))
    if filters.source_id is not None:
        query = query.where(Member.source_id == filters.source_id)
    if filters.city and filters.city.strip():
        query = query.where(Member.city.collate("NOCASE") == filters.city.strip())
    if filters.status and filters.status.strip():
        query = query.where(Member.status == filters.status.strip().lower())
    return [respondent_summary(*row) for row in db.execute(query)]


def respondent_summary(
    member: Member, source: Source, referral: Referral | None, referrer: Member | None,
) -> Respondent:
    return Respondent(
        id=member.id,
        name=member.name,
        phone=member.phone_e164,
        city=member.city,
        source=SourceSummary(id=source.id, name=source.name),
        status=member.status,
        profile_complete=member.profile_completed_at is not None,
        referral=StaffReferral(
            id=referral.id,
            stage=referral.stage,
            verification_status=referral.verification_status,
            claimed_name=referral.claimed_name,
            referrer=StaffReferrer(id=referrer.id, name=referrer.name) if referrer else None,
            failure_reason=referral.failure_reason,
        ) if referral else None,
    )


def list_filter_options(db: Session) -> RespondentFilters:
    sources = db.scalars(select(Source).order_by(Source.name)).all()
    city = Member.city.collate("NOCASE")
    return RespondentFilters(
        sources=[SourceSummary(id=source.id, name=source.name) for source in sources],
        cities=list(db.scalars(
            select(city).where(Member.city.is_not(None), Member.city != "").distinct().order_by(city)
        )),
        statuses=list(db.scalars(select(Member.status).distinct().order_by(Member.status))),
    )


@router.get("/admin/respondents")
def respondents(
    db: Database, _staff: CurrentStaff, filters: Annotated[RespondentQuery, Query()],
) -> RespondentGrid:
    return RespondentGrid(respondents=matching_respondents(db, filters), filters=list_filter_options(db))


def spreadsheet_cell(value: str | None) -> str:
    if value is None:
        return ""
    formula_prefixes = ("=", "+", "-", "@", "＝", "＋", "－", "＠")
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(formula_prefixes):
        return "'" + value
    return value


@router.get("/admin/respondents/export", response_class=Response)
def export_respondents(
    db: Database, _staff: CurrentStaff, filters: Annotated[RespondentQuery, Query()],
) -> Response:
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("id", "name", "phone", "city", "source", "status", "profile_complete", "referral_stage"))
    for member in matching_respondents(db, filters):
        writer.writerow((
            member.id,
            spreadsheet_cell(member.name),
            spreadsheet_cell(member.phone),
            spreadsheet_cell(member.city),
            spreadsheet_cell(member.source.name),
            spreadsheet_cell(member.status),
            member.profile_complete,
            spreadsheet_cell(member.referral.stage) if member.referral else "",
        ))
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="viewbox-respondents.csv"'},
    )


@router.get("/admin/respondents/{member_id}")
def respondent_detail(member_id: int, db: Database, _staff: CurrentStaff) -> RespondentDetail:
    row = db.execute(respondent_query().where(Member.id == member_id)).one_or_none()
    if row is None:
        raise api_error(404, "member_not_found", "That respondent does not exist.")
    participations = db.execute(
        select(Participation, Survey.title)
        .join(Survey, Survey.id == Participation.survey_id)
        .where(Participation.member_id == member_id)
        .order_by(Participation.applied_at.desc(), Participation.id.desc())
    )
    return RespondentDetail(
        **respondent_summary(*row).model_dump(),
        participations=[
            StaffParticipation(
                id=participation.id,
                survey_id=participation.survey_id,
                survey_title=title,
                eligibility_status=participation.eligibility_status,
                fit_at=participation.fit_at.replace(tzinfo=UTC) if participation.fit_at else None,
                completed_at=participation.completed_at.replace(tzinfo=UTC) if participation.completed_at else None,
            )
            for participation, title in participations
        ],
    )


def approved_participation(db: Session, participation_id: int) -> Participation:
    participation = db.get(Participation, participation_id)
    if participation is None:
        raise api_error(404, "participation_not_found", "That survey application does not exist.")
    if participation.eligibility_status != "approved":
        raise api_error(409, "participation_not_approved", "This application must be approved first.")
    return participation


def referral_for_member(db: Session, member_id: int) -> Referral | None:
    return db.scalar(select(Referral).where(Referral.referred_member_id == member_id))


def bind_referral_to_first_fit(db: Session, referral: Referral) -> None:
    first_fit = db.scalar(
        select(Participation)
        .where(
            Participation.member_id == referral.referred_member_id,
            Participation.eligibility_status == "approved",
            Participation.fit_at.is_not(None),
        )
        .order_by(Participation.fit_at, Participation.id)
        .limit(1)
    )
    if first_fit is not None:
        referral.participation_id = first_fit.id
        referral.stage = "completed" if first_fit.completed_at is not None else "fit"


@router.post("/admin/participations/{participation_id}/fit", status_code=204)
def mark_fit(participation_id: int, db: Database, staff: CurrentStaff) -> None:
    lock_for_write(db)
    participation = approved_participation(db, participation_id)
    if participation.fit_at is None:
        participation.fit_at = now_utc()
        participation.fit_by_id = staff.id
    referral = referral_for_member(db, participation.member_id)
    if referral and referral.verification_status == "verified" and referral.stage == "lead":
        bind_referral_to_first_fit(db, referral)
    db.commit()


@router.post("/admin/participations/{participation_id}/complete", status_code=204)
def mark_complete(participation_id: int, db: Database, staff: CurrentStaff) -> None:
    lock_for_write(db)
    participation = approved_participation(db, participation_id)
    if participation.fit_at is None:
        raise api_error(409, "participation_not_fit", "Mark this respondent Fit before confirming completion.")
    if participation.completed_at is None:
        participation.completed_at = now_utc()
        participation.completed_by_id = staff.id
    referral = referral_for_member(db, participation.member_id)
    if (
        referral
        and referral.verification_status == "verified"
        and referral.stage == "fit"
        and referral.participation_id == participation.id
    ):
        referral.stage = "completed"
    db.commit()


def get_referral(db: Session, referral_id: int) -> Referral:
    referral = db.get(Referral, referral_id)
    if referral is None:
        raise api_error(404, "referral_not_found", "That referral does not exist.")
    return referral


@router.post("/admin/referrals/{referral_id}/review", status_code=204)
def review_referral(referral_id: int, data: ReferralReview, db: Database, _staff: CurrentStaff) -> None:
    lock_for_write(db)
    referral = get_referral(db, referral_id)
    if referral.verification_status != "pending":
        same_approval = (
            data.referrer_member_id is not None
            and referral.verification_status == "verified"
            and referral.referrer_member_id == data.referrer_member_id
        )
        same_rejection = (
            data.failure_reason is not None
            and referral.verification_status == "rejected"
            and referral.failure_reason == data.failure_reason
        )
        if same_approval or same_rejection:
            return
        raise api_error(409, "referral_already_reviewed", "This referral claim has already been reviewed.")

    if data.referrer_member_id is None:
        referral.verification_status = "rejected"
        referral.stage = "failed"
        referral.failure_reason = data.failure_reason
    else:
        if data.referrer_member_id == referral.referred_member_id:
            raise api_error(422, "self_referral", "A respondent cannot refer themselves.")
        if db.get(Member, data.referrer_member_id) is None:
            raise api_error(422, "referrer_not_found", "No member has that ID.")
        referral.referrer_member_id = data.referrer_member_id
        referral.verification_status = "verified"
        referral.stage = "lead"
        bind_referral_to_first_fit(db, referral)
    db.commit()


@router.post("/admin/referrals/{referral_id}/fail", status_code=204)
def fail_referral(referral_id: int, data: ReferralFailure, db: Database, _staff: CurrentStaff) -> None:
    lock_for_write(db)
    referral = get_referral(db, referral_id)
    if referral.verification_status != "verified":
        raise api_error(409, "referral_not_verified", "Review this referral claim before marking it failed.")
    if referral.stage == "failed" and referral.failure_reason == data.reason:
        return
    if referral.stage not in {"lead", "fit"}:
        raise api_error(409, "referral_closed", "This referral is already closed.")
    referral.stage = "failed"
    referral.failure_reason = data.reason
    db.commit()


@router.get("/admin/source-stats")
def source_stats(db: Database, _staff: CurrentStaff) -> list[SourceStats]:
    totals = db.execute(
        select(
            Source.id,
            Source.name,
            func.count(distinct(Member.id)),
            func.count(distinct(case((Participation.fit_at.is_not(None), Member.id)))),
            func.count(distinct(case((Participation.completed_at.is_not(None), Member.id)))),
        )
        .select_from(Source)
        .outerjoin(Member, Member.source_id == Source.id)
        .outerjoin(Participation, Participation.member_id == Member.id)
        .group_by(Source.id, Source.name)
        .order_by(Source.name)
    )
    return [
        SourceStats(id=source_id, name=name, signups=signups, fit=fit, completed=completed)
        for source_id, name, signups, fit, completed in totals
    ]


def masked_phone(phone: str) -> str:
    digits = phone[3:] if phone.startswith("+91") else phone.removeprefix("+")
    return f"{digits[:2]}{'X' * (len(digits) - 4)}{digits[-2:]}"


@router.get("/member/referrals")
def member_referrals(db: Database, member: CurrentMember) -> list[MemberReferral]:
    referred_members = db.execute(
        select(Referral, Member)
        .join(Member, Member.id == Referral.referred_member_id)
        .where(
            Referral.referrer_member_id == member.id,
            Referral.verification_status == "verified",
            Referral.stage.is_not(None),
        )
        .order_by(Referral.id.desc())
    )
    return [
        MemberReferral(
            id=referral.id,
            name=referred.name,
            phone_masked=masked_phone(referred.phone_e164),
            stage=referral.stage,
            failure_reason=referral.failure_reason,
        )
        for referral, referred in referred_members
    ]
