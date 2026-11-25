from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field, StrictInt, StringConstraints, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .db import lock_for_write
from .dependencies import CurrentAdmin, CurrentMember, Database
from .models import Interest, Member, MemberInterest
from .security import api_error, now_utc
from .survey_models import Participation, Survey, SurveyRule

router = APIRouter(prefix="/api", tags=["Surveys"])

RuleField = Literal["age", "city", "gender", "income_range"]
RuleMode = Literal["strict", "flexible"]
SavedStatus = Literal["approved", "waitlisted"]
EligibilityStatus = Literal["approved", "waitlisted", "rejected"]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
InterestName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
SURVEY_MAX_DURATION = timedelta(days=15)
INCOME_LABELS = {
    "under_25000": "below ₹25,000",
    "25000_50000": "₹25,000–₹50,000",
    "50000_100000": "₹50,000–₹1,00,000",
    "over_100000": "above ₹1,00,000",
}


def unique_labels(labels: list[str]) -> list[str]:
    result: dict[str, str] = {}
    for label in labels:
        result.setdefault(label.casefold(), label)
    return list(result.values())


class RuleBody(BaseModel):
    field: RuleField
    mode: RuleMode
    values: list[StrictInt | str] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_values(self) -> "RuleBody":
        if self.field == "age":
            if len(self.values) != 2 or any(type(value) is not int for value in self.values):
                raise ValueError("Age rules need two whole numbers: minimum and maximum age.")
            low, high = self.values
            if not 0 <= low <= high:
                raise ValueError("The minimum age must be non-negative and no greater than the maximum.")
        else:
            if any(not isinstance(value, str) or not value.strip() or len(value.strip()) > 100
                   for value in self.values):
                raise ValueError("Enter non-empty text values for this rule.")
            self.values = unique_labels([value.strip() for value in self.values])
        return self


class SurveyBody(BaseModel):
    title: Title
    description: Description
    opens_at: datetime
    closes_at: datetime
    quota: Annotated[StrictInt, Field(gt=0, le=2_147_483_647)]
    published: bool = False
    interests: list[InterestName] = Field(default_factory=list, max_length=30)
    rules: list[RuleBody] = Field(default_factory=list, max_length=4)

    @field_validator("opens_at", "closes_at")
    @classmethod
    def normalize_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value
        try:
            return value.astimezone(UTC).replace(tzinfo=None)
        except (OverflowError, ValueError) as error:
            raise ValueError("Enter a valid survey date and time.") from error

    @model_validator(mode="after")
    def validate_window_and_rules(self) -> "SurveyBody":
        if self.closes_at <= self.opens_at:
            raise ValueError("The survey must close after it opens.")
        if self.closes_at - self.opens_at > SURVEY_MAX_DURATION:
            raise ValueError("A survey can run for at most 15 days.")
        if len({rule.field for rule in self.rules}) != len(self.rules):
            raise ValueError("Add at most one rule per field.")
        return self


class PublishBody(BaseModel):
    published: bool


class SurveySummary(BaseModel):
    id: int
    title: str
    description: str
    opens_at: datetime
    closes_at: datetime
    quota: int


class AdminSurvey(SurveySummary):
    published: bool
    interests: list[str]
    rules: list[RuleBody]


class Eligibility(BaseModel):
    status: EligibilityStatus
    reason: str
    eligible_on: date | None = None


class ParticipationSummary(BaseModel):
    id: int
    eligibility_status: SavedStatus
    fit_at: datetime | None
    completed_at: datetime | None


class MemberSurvey(SurveySummary):
    live: bool
    interest_match: bool
    eligibility: Eligibility
    participation: ParticipationSummary | None


@dataclass(frozen=True)
class MemberContext:
    member: Member
    time: datetime
    interest_ids: set[int]
    eligible_on: date | None


def utc_time(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC)


def survey_summary(survey: Survey) -> SurveySummary:
    return SurveySummary(
        id=survey.id,
        title=survey.title,
        description=survey.description,
        opens_at=utc_time(survey.opens_at),
        closes_at=utc_time(survey.closes_at),
        quota=survey.quota,
    )


def admin_survey_summary(survey: Survey) -> AdminSurvey:
    return AdminSurvey(
        **survey_summary(survey).model_dump(),
        published=survey.published,
        interests=[interest.name for interest in survey.interests],
        rules=[
            RuleBody(field=rule.field, mode=rule.mode, values=rule.allowed_values)
            for rule in survey.rules
        ],
    )


def survey_query():
    return select(Survey).options(selectinload(Survey.rules), selectinload(Survey.interests))


def get_survey(db: Session, survey_id: int) -> Survey:
    survey = db.scalar(survey_query().where(Survey.id == survey_id))
    if survey is None:
        raise api_error(404, "survey_not_found", "This survey is not available.")
    return survey


def survey_is_live(survey: Survey, time: datetime) -> bool:
    return survey.published and survey.opens_at <= time < survey.closes_at


def add_cool_off(completed_on: date) -> date:
    year_delta, month_index = divmod(completed_on.month - 1 + 3, 12)
    year, month = completed_on.year + year_delta, month_index + 1
    return date(year, month, min(completed_on.day, monthrange(year, month)[1]))


def member_context(db: Session, member: Member, time: datetime) -> MemberContext:
    latest_completion = db.scalar(
        select(func.max(Participation.completed_at)).where(Participation.member_id == member.id)
    )
    completion_dates = [
        value for value in (
            member.imported_last_completed_on,
            latest_completion.date() if latest_completion else None,
        ) if value is not None
    ]
    cooldown_ends = add_cool_off(max(completion_dates)) if completion_dates else None
    interest_ids = set(db.scalars(
        select(MemberInterest.interest_id).where(MemberInterest.member_id == member.id)
    ))
    return MemberContext(member, time, interest_ids, cooldown_ends)


def age_on(birth_date: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (birth_date.month, birth_date.day)
    return today.year - birth_date.year - (not had_birthday)


def rule_mismatch(rule: SurveyRule, member: Member, today: date) -> str | None:
    if rule.field == "age":
        low, high = rule.allowed_values
        if member.date_of_birth is not None:
            age = age_on(member.date_of_birth, today)
            if low <= age <= high:
                return None
            return f"Your age is {age}. This survey asks for ages {low} to {high}."
        return "This survey requires a date of birth."

    current = getattr(member, rule.field)
    allowed = rule.allowed_values
    if current is not None and current.strip().casefold() in {value.casefold() for value in allowed}:
        return None
    label = {"city": "cities", "gender": "genders", "income_range": "income ranges"}[rule.field]
    values = (
        INCOME_LABELS.get(value, value.replace("_", " ")) if rule.field == "income_range"
        else value.replace("_", " ")
        for value in allowed
    )
    return f"This survey asks for these {label}: {', '.join(values)}."


def eligibility_for(survey: Survey, context: MemberContext, taken: int) -> Eligibility:
    member, time = context.member, context.time
    if not survey_is_live(survey, time):
        message = "This survey has closed." if time >= survey.closes_at else "This survey is not open."
        return Eligibility(status="rejected", reason=message)
    if member.profile_completed_at is None:
        return Eligibility(status="rejected", reason="Complete your profile before applying.")
    if context.eligible_on is not None and time.date() < context.eligible_on:
        return Eligibility(
            status="rejected",
            reason=f"Your three-month cool-off ends on {context.eligible_on:%d %b %Y}.",
            eligible_on=context.eligible_on,
        )
    if taken >= survey.quota:
        return Eligibility(status="rejected", reason="All survey spots are filled.")

    first_flexible_mismatch = None
    for rule in survey.rules:
        mismatch = rule_mismatch(rule, member, time.date())
        if mismatch and rule.mode == "strict":
            return Eligibility(status="rejected", reason=mismatch)
        if mismatch and first_flexible_mismatch is None:
            first_flexible_mismatch = mismatch
    if first_flexible_mismatch is not None:
        return Eligibility(status="waitlisted", reason=first_flexible_mismatch)
    return Eligibility(status="approved", reason="Your profile meets the survey requirements.")


def member_survey_summary(
    survey: Survey,
    context: MemberContext,
    taken: int,
    participation: Participation | None,
) -> MemberSurvey:
    saved = None
    if participation is None:
        eligibility = eligibility_for(survey, context, taken)
    else:
        eligibility = Eligibility(
            status=participation.eligibility_status, reason=participation.eligibility_reason
        )
        saved = ParticipationSummary(
            id=participation.id,
            eligibility_status=participation.eligibility_status,
            fit_at=utc_time(participation.fit_at) if participation.fit_at else None,
            completed_at=utc_time(participation.completed_at) if participation.completed_at else None,
        )
    return MemberSurvey(
        **survey_summary(survey).model_dump(),
        live=survey_is_live(survey, context.time),
        interest_match=any(interest.id in context.interest_ids for interest in survey.interests),
        eligibility=eligibility,
        participation=saved,
    )


def approved_counts(db: Session, survey_ids: list[int]) -> dict[int, int]:
    if not survey_ids:
        return {}
    rows = db.execute(
        select(Participation.survey_id, func.count())
        .where(Participation.survey_id.in_(survey_ids), Participation.eligibility_status == "approved")
        .group_by(Participation.survey_id)
    )
    return {survey_id: count for survey_id, count in rows}


def member_participation(db: Session, survey: Survey, member: Member) -> Participation | None:
    return db.scalar(select(Participation).where(
        Participation.survey_id == survey.id, Participation.member_id == member.id
    ))


@router.get("/admin/surveys")
def admin_surveys(db: Database, _admin: CurrentAdmin) -> list[AdminSurvey]:
    surveys = db.scalars(survey_query().order_by(Survey.opens_at.desc(), Survey.id.desc()))
    return [admin_survey_summary(survey) for survey in surveys]


@router.post("/admin/surveys", status_code=status.HTTP_201_CREATED)
def admin_create_survey(body: SurveyBody, db: Database, _admin: CurrentAdmin) -> AdminSurvey:
    lock_for_write(db)
    survey = Survey(**body.model_dump(exclude={"rules", "interests"}))
    survey.rules = [
        SurveyRule(field=rule.field, mode=rule.mode, allowed_values=rule.values)
        for rule in body.rules
    ]
    for name in unique_labels(body.interests):
        interest = db.scalar(select(Interest).where(Interest.name == name))
        survey.interests.append(interest if interest is not None else Interest(name=name))
    db.add(survey)
    db.commit()
    return admin_survey_summary(survey)


@router.patch("/admin/surveys/{survey_id}/publish")
def admin_publish_survey(
    survey_id: int, body: PublishBody, db: Database, _admin: CurrentAdmin
) -> AdminSurvey:
    lock_for_write(db)
    survey = get_survey(db, survey_id)
    survey.published = body.published
    db.commit()
    return admin_survey_summary(survey)


@router.get("/member/surveys")
def member_surveys(db: Database, member: CurrentMember) -> list[MemberSurvey]:
    time = now_utc()
    participations = {
        entry.survey_id: entry
        for entry in db.scalars(select(Participation).where(Participation.member_id == member.id))
    }
    surveys = db.scalars(
        survey_query().where(or_(
            Survey.published.is_(True) & (Survey.opens_at <= time) & (Survey.closes_at > time),
            Survey.id.in_(participations.keys()),
        )).order_by(Survey.closes_at, Survey.id)
    ).all()
    context = member_context(db, member, time)
    counts = approved_counts(db, [survey.id for survey in surveys if survey.id not in participations])
    summaries = [
        member_survey_summary(survey, context, counts.get(survey.id, 0), participations.get(survey.id))
        for survey in surveys
    ]
    return sorted(summaries, key=lambda result: (not result.live, not result.interest_match))


@router.get("/member/surveys/{survey_id}")
def member_survey(survey_id: int, db: Database, member: CurrentMember) -> MemberSurvey:
    survey = get_survey(db, survey_id)
    time = now_utc()
    participation = member_participation(db, survey, member)
    if not survey_is_live(survey, time) and participation is None:
        raise api_error(404, "survey_not_found", "This survey is not available.")
    context = member_context(db, member, time)
    taken = approved_counts(db, [survey.id]).get(survey.id, 0) if participation is None else 0
    return member_survey_summary(survey, context, taken, participation)


@router.post("/member/surveys/{survey_id}/apply")
def member_apply(survey_id: int, db: Database, member: CurrentMember) -> MemberSurvey:
    lock_for_write(db)
    db.refresh(member)
    survey = get_survey(db, survey_id)
    time = now_utc()
    participation = member_participation(db, survey, member)
    if not survey.published and participation is None:
        raise api_error(404, "survey_not_found", "This survey is not available.")

    context = member_context(db, member, time)
    taken = approved_counts(db, [survey.id]).get(survey.id, 0) if participation is None else 0
    result = member_survey_summary(survey, context, taken, participation)
    if participation is not None or result.eligibility.status == "rejected":
        db.rollback()
        return result

    participation = Participation(
        member_id=member.id,
        survey_id=survey.id,
        eligibility_status=result.eligibility.status,
        eligibility_reason=result.eligibility.reason,
        applied_at=time,
    )
    db.add(participation)
    db.commit()
    return member_survey_summary(survey, context, taken, participation)
