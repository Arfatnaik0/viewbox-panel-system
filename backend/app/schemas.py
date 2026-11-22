from datetime import date
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from .security import normalize_phone, now_utc

PhoneText = Annotated[str, StringConstraints(min_length=1, max_length=50)]
TokenText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
NameText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ProfileText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
InterestText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class OtpRequest(BaseModel):
    phone: PhoneText

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, phone: str) -> str:
        return normalize_phone(phone)


class OtpVerify(BaseModel):
    challenge_id: TokenText
    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]
    source_token: TokenText | None = None
    source_id: int | None = None
    referrer_name: NameText | None = None


class ProfileUpdate(BaseModel):
    name: NameText
    date_of_birth: date
    gender: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    city: ProfileText
    income_range: ProfileText
    interests: list[InterestText]

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, birth_date: date) -> date:
        if birth_date > now_utc().date():
            raise ValueError("Date of birth cannot be in the future.")
        return birth_date

    @field_validator("interests")
    @classmethod
    def deduplicate_interests(cls, interests: list[str]) -> list[str]:
        unique: dict[str, str] = {}
        for interest in interests:
            unique.setdefault(interest.casefold(), interest)
        return list(unique.values())


class AdminLogin(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=256)]


class SourceCreate(BaseModel):
    name: ProfileText


class SourceSummary(BaseModel):
    id: int
    name: str


class AdminSource(SourceSummary):
    token: str


class SignupLinkSummary(BaseModel):
    source: SourceSummary
    personal: bool


class MemberSummary(BaseModel):
    id: int
    phone: str
    name: str | None
    date_of_birth: date | None
    gender: str | None
    city: str | None
    income_range: str | None
    interests: list[str]
    profile_complete: bool
    source: SourceSummary
    referral_token: str


class OtpIssued(BaseModel):
    challenge_id: str
    demo_code: str


class AdminSummary(BaseModel):
    email: str
