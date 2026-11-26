import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.errors import HeaderParseError
from email.headerregistry import Address
from typing import Annotated

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field, StringConstraints, field_validator
from sqlalchemy import select

from .attribution import ensure_personal_link, ensure_source
from .db import lock_for_write
from .dependencies import CurrentAdmin, Database
from .meta_models import MetaLead
from .models import Member
from .security import api_error, normalize_phone, now_utc

router = APIRouter(prefix="/api/integrations/meta", tags=["Meta Ads"])
Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
FormFieldName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
FormFieldValue = Annotated[str, StringConstraints(max_length=4096)]
DOMAIN_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")


class MetaFormField(BaseModel):
    name: FormFieldName
    values: list[FormFieldValue] = Field(min_length=1, max_length=50)


class MetaLeadRecord(BaseModel):
    id: Identifier
    form_id: Identifier
    campaign_id: Identifier
    ad_id: Identifier | None = None
    created_time: datetime
    field_data: list[MetaFormField] = Field(min_length=1, max_length=100)

    @field_validator("created_time", mode="before")
    @classmethod
    def parse_created_time(cls, value: object) -> datetime:
        if isinstance(value, str) and "T" in value:
            try:
                parsed = datetime.fromisoformat(value)
                if parsed.tzinfo is not None:
                    return parsed.astimezone(UTC)
            except (ValueError, OverflowError):
                pass
        raise ValueError("Use an ISO datetime with a timezone for created_time.")


class MetaLeadResult(BaseModel):
    lead_id: str
    member_id: int
    campaign_id: str
    created_member: bool
    duplicate: bool


@dataclass(frozen=True)
class LeadContact:
    name: str
    phone: str
    city: str
    email: str | None


def single_value(fields: dict[str, list[str]], key: str, limit: int) -> str:
    values = fields.get(key, [])
    if len(values) != 1 or not values[0].strip() or len(values[0].strip()) > limit:
        raise api_error(422, "invalid_meta_field", f"Provide one non-empty value for {key}.")
    return values[0].strip()


def validate_email(email: str) -> None:
    try:
        address = Address(addr_spec=email)
        labels = address.domain.encode("idna").decode("ascii").split(".")
        if address.username and len(labels) > 1 and all(DOMAIN_LABEL.fullmatch(part) for part in labels):
            return
    except (ValueError, HeaderParseError):
        pass
    raise api_error(422, "invalid_meta_field", "Provide a valid email address.")


def read_contact(field_data: list[MetaFormField]) -> LeadContact:
    fields: dict[str, list[str]] = {}
    for field in field_data:
        key = field.name.casefold()
        if key in fields:
            raise api_error(422, "duplicate_meta_field", f"The form contains multiple {key} fields.")
        fields[key] = field.values

    name = single_value(fields, "full_name", 120)
    city = single_value(fields, "city", 100)
    phone_value = single_value(fields, "phone_number", 50)
    try:
        phone = normalize_phone(phone_value)
    except ValueError as exc:
        raise api_error(422, "invalid_meta_field", str(exc)) from exc
    email = single_value(fields, "email", 254) if "email" in fields else None
    if email is not None:
        validate_email(email)
    return LeadContact(name=name, phone=phone, city=city, email=email)


def lead_result(lead: MetaLead, *, duplicate: bool) -> MetaLeadResult:
    return MetaLeadResult(
        lead_id=lead.lead_id,
        member_id=lead.member_id,
        campaign_id=lead.campaign_id,
        created_member=lead.created_member,
        duplicate=duplicate,
    )


@router.post(
    "/leads",
    status_code=status.HTTP_201_CREATED,
    responses={200: {"model": MetaLeadResult, "description": "Previously accepted delivery"}},
)
def receive_meta_lead(
    record: MetaLeadRecord, response: Response, db: Database, _admin: CurrentAdmin
) -> MetaLeadResult:
    contact = read_contact(record.field_data)
    lock_for_write(db)

    saved_lead = db.get(MetaLead, record.id)
    if saved_lead is not None:
        result = lead_result(saved_lead, duplicate=True)
        db.rollback()
        response.status_code = status.HTTP_200_OK
        return result

    member = db.scalar(select(Member).where(Member.phone_e164 == contact.phone))
    created_member = member is None
    if member is None:
        source = ensure_source(db, "Meta Ads")
        member = Member(
            phone_e164=contact.phone,
            name=contact.name,
            email=contact.email,
            city=contact.city,
            source_id=source.id,
            joined_at=now_utc(),
        )
        db.add(member)
        db.flush()
        ensure_personal_link(db, member)
    else:
        for field in ("name", "city", "email"):
            previous = getattr(member, field)
            if previous is None or not previous.strip():
                setattr(member, field, getattr(contact, field))

    lead = MetaLead(
        lead_id=record.id,
        member_id=member.id,
        form_id=record.form_id,
        campaign_id=record.campaign_id,
        ad_id=record.ad_id,
        submitted_at=record.created_time.replace(tzinfo=None),
        created_member=created_member,
    )
    db.add(lead)
    db.commit()
    return lead_result(lead, duplicate=False)
