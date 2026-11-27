import csv
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time
from io import StringIO
from itertools import islice
from typing import Annotated, Literal

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .attribution import ensure_personal_link, ensure_source
from .db import lock_for_write
from .dependencies import CurrentStaff, Database
from .legacy_models import LegacyMemberKey, LegacyReferralKey
from .models import Interest, Member, MemberInterest, Referral
from .operations import bind_referral_to_first_fit
from .security import api_error, normalize_phone, now_utc


router = APIRouter(prefix="/api", tags=["CSV import"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
MAX_RECORD_LINES = 12
MAX_COLUMNS = 100
FALLBACK_SOURCE = "Legacy Import"

CITY_ALIASES = {
    **{city.casefold(): city for city in (
        "Ahmedabad", "Bengaluru", "Delhi", "Hyderabad", "Mumbai", "Nagpur", "Nashik",
        "Navi Mumbai", "Pune", "Thane",
    )},
    "bangalore": "Bengaluru",
    "bombay": "Mumbai",
    "navimumbai": "Navi Mumbai",
}
GENDER_ALIASES = {
    "f": "female", "female": "female", "woman": "female",
    "m": "male", "male": "male", "man": "male",
    "non-binary": "non_binary", "non_binary": "non_binary", "non binary": "non_binary",
    "prefer not to say": "prefer_not_to_say", "prefer_not_to_say": "prefer_not_to_say",
}
INCOME_ALIASES = {
    "below3l": "annual_under_3l",
    "3l-6l": "annual_3l_6l",
    "6l-10l": "annual_6l_10l",
    "10l-20l": "annual_10l_20l",
    "above20l": "annual_over_20l",
    "below25000": "under_25000", "under25000": "under_25000",
    "25000-50000": "25000_50000",
    "50000-100000": "50000_100000",
    "above100000": "over_100000", "over100000": "over_100000",
    "prefernottosay": "prefer_not_to_say",
}
INCOME_CODES = set(INCOME_ALIASES.values())
SOURCE_ALIASES = {
    "facebook": "Facebook", "fb": "Facebook",
    "instagram": "Instagram", "ig": "Instagram", "insta": "Instagram",
    "website": "Website",
    "referral": "Member Referral", "member referral": "Member Referral",
    "mumbai whatsapp": "Mumbai WhatsApp", "whatsapp mumbai": "Mumbai WhatsApp",
    "whatsapp group - mumbai": "Mumbai WhatsApp", "wa grp mumbai": "Mumbai WhatsApp",
    "whatsapp group - pune": "WhatsApp Group - Pune",
    "legacy import": FALLBACK_SOURCE,
}
INTEREST_ALIASES = {
    **{interest.casefold(): interest for interest in (
        "Auto", "Beauty", "Entertainment", "Fashion", "Finance", "Food & beverages",
        "Health & wellness", "Home", "Kids", "Shopping", "Technology", "Travel",
    )},
    "food": "Food & beverages", "food and beverages": "Food & beverages",
    "health": "Health & wellness", "health and wellness": "Health & wellness",
    "tech": "Technology",
}
NULL_TEXT = {"", "n/a", "null", "-"}
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%m-%y", "%d/%m/%y")
EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")


class ImportSummary(BaseModel):
    total: int = 0
    created: int = 0
    matched: int = 0
    fixed: int = 0
    skipped: int = 0


class RowIssue(BaseModel):
    row: int
    action: Literal["fixed", "skipped", "notice"]
    reason: str


class ImportResult(BaseModel):
    preview: bool
    summary: ImportSummary = Field(default_factory=ImportSummary)
    issues: list[RowIssue] = Field(default_factory=list)

    def report(self, row: int, action: Literal["fixed", "skipped", "notice"], reason: str) -> None:
        self.issues.append(RowIssue(row=row, action=action, reason=reason))


@dataclass
class CsvRow:
    number: int
    values: dict[str, str]
    fixes: list[str] = field(default_factory=list)

    def text(self, key: str, limit: int, label: str) -> str | None:
        raw = self.values.get(key, "")
        cleaned = " ".join(raw.split())
        if cleaned.casefold() in NULL_TEXT:
            return None
        if len(cleaned) > limit or any(ord(char) < 32 for char in cleaned):
            self.fixes.append(f"Ignored invalid {label}.")
            return None
        if raw != cleaned:
            self.fixes.append(f"Cleaned whitespace in {label}.")
        return cleaned

    def date(self, key: str, label: str, today: date) -> date | None:
        value = self.text(key, 30, label)
        if value is None:
            return None
        for pattern in DATE_FORMATS:
            try:
                parsed = datetime.strptime(value, pattern).date()
            except ValueError:
                continue
            if date(1900, 1, 1) <= parsed <= today:
                if parsed.isoformat() != value:
                    self.fixes.append(f"Normalized {label}.")
                return parsed
        self.fixes.append(f"Ignored invalid or future {label}.")
        return None


@dataclass
class BoundRow:
    row: int
    member_id: int
    legacy_id: str | None
    referrer_key: str | None


def parse_csv(content: bytes, result: ImportResult) -> list[CsvRow]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise api_error(422, "invalid_csv_encoding", "Upload a UTF-8 CSV file.") from error
    line_limit = MAX_ROWS * MAX_RECORD_LINES + 1
    lines = list(islice(StringIO(text, newline=""), line_limit + 1))
    if len(lines) > line_limit:
        raise api_error(413, "too_many_csv_rows", f"Upload no more than {MAX_ROWS:,} CSV rows.")
    try:
        columns = [name.strip().casefold() for name in next(csv.reader(lines[:1], strict=True))]
    except (csv.Error, StopIteration) as error:
        raise api_error(422, "invalid_csv_header", "The file needs a CSV header containing phone.") from error
    if "phone" not in columns or len(columns) != len(set(columns)) or len(columns) > MAX_COLUMNS:
        raise api_error(422, "invalid_csv_header", "The CSV header needs unique columns including phone.")

    parsed = []
    index = 1
    while index < len(lines):
        result.summary.total += 1
        if result.summary.total > MAX_ROWS:
            raise api_error(413, "too_many_csv_rows", f"Upload no more than {MAX_ROWS:,} CSV rows.")
        number = result.summary.total + 1
        reader = csv.reader(lines[index:index + MAX_RECORD_LINES], strict=True)
        try:
            values = next(reader)
        except csv.Error:
            # Recover at the next line if quoting ran into later records.
            index += 1
            result.summary.skipped += 1
            result.report(number, "skipped", "Malformed CSV quoting or record is too large.")
            continue
        index += reader.line_num
        if len(values) != len(columns):
            result.summary.skipped += 1
            result.report(number, "skipped", "The column count does not match the header.")
        else:
            parsed.append(CsvRow(number, dict(zip(columns, values))))
    return parsed


def clean_email(row: CsvRow) -> str | None:
    email = row.text("email", 254, "email")
    if email is None:
        return None
    if not EMAIL.fullmatch(email):
        row.fixes.append("Ignored an invalid email address.")
        return None
    local, domain = email.rsplit("@", 1)
    if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local or any(
        label.startswith("-") or label.endswith("-") or len(label) > 63 for label in domain.split(".")
    ):
        row.fixes.append("Ignored an invalid email address.")
        return None
    if domain != domain.lower():
        row.fixes.append("Normalized the email domain.")
    return f"{local}@{domain.lower()}"


def choice(row: CsvRow, key: str, label: str, max_length: int, aliases: dict[str, str]) -> str | None:
    value = row.text(key, max_length, label)
    if value is None:
        return None
    clean = aliases.get(value.casefold(), value)
    if clean != value:
        row.fixes.append(f"Normalized {label}.")
    return clean


def clean_income(row: CsvRow) -> str | None:
    value = row.text("income_range", 100, "income range")
    if value is None or value in INCOME_CODES:
        return value
    compact = re.sub(r"[₹,\s]", "", value.casefold()).replace("–", "-").replace("—", "-")
    normalized = INCOME_ALIASES.get(compact)
    if normalized is None:
        row.fixes.append("Left an unrecognized income range for the member to confirm.")
    else:
        row.fixes.append("Normalized the income range.")
    return normalized


def clean_interests(row: CsvRow) -> list[str]:
    raw = row.text("interests", 3000, "interests")
    if raw is None:
        return []
    names: dict[str, str] = {}
    parts = re.split(r"[,;|]", raw)
    cleaned = False
    for part in parts:
        name = part.strip()
        canonical = INTEREST_ALIASES.get(name.casefold(), name)
        if not name or len(name) > 80 or canonical.casefold() in names or len(names) >= 30:
            cleaned = True
            continue
        names[canonical.casefold()] = canonical
        cleaned = cleaned or name != canonical
    if cleaned:
        row.fixes.append("Cleaned interest labels or removed duplicate or invalid interests.")
    return list(names.values())


def apply_member_fields(db: Session, member: Member, row: CsvRow, today: date) -> None:
    gender = choice(row, "gender", "gender", 60, GENDER_ALIASES)
    if gender is not None and gender not in GENDER_ALIASES.values():
        row.fixes.append("Left an unrecognized gender value for the member to confirm.")
        gender = None
    fields = {
        "name": row.text("name", 120, "name"),
        "email": clean_email(row),
        "date_of_birth": row.date("date_of_birth", "date of birth", today),
        "gender": gender,
        "city": choice(row, "city", "city", 100, CITY_ALIASES),
        "income_range": clean_income(row),
    }
    for key, value in fields.items():
        if value is not None and not getattr(member, key):
            setattr(member, key, value)
    completion = row.date("last_survey_completed_on", "last survey completion date", today)
    if completion and (member.imported_last_completed_on is None or completion > member.imported_last_completed_on):
        member.imported_last_completed_on = completion

    interests = clean_interests(row)
    has_interests = db.scalar(select(MemberInterest.member_id).where(
        MemberInterest.member_id == member.id
    ).limit(1)) is not None
    if not has_interests and interests:
        for name in interests:
            interest = db.scalar(select(Interest).where(Interest.name == name))
            if interest is None:
                interest = Interest(name=name)
                db.add(interest)
                db.flush()
            db.add(MemberInterest(member_id=member.id, interest_id=interest.id))
        has_interests = True
    if member.profile_completed_at is None and has_interests and all((
        member.name, member.date_of_birth, member.gender, member.city, member.income_range,
    )):
        member.profile_completed_at = now_utc()


def bind_members(db: Session, rows: list[CsvRow], result: ImportResult) -> list[BoundRow]:
    bound = []
    seen_phones: set[str] = set()
    today = now_utc().date()
    for row in rows:
        raw_phone = row.values["phone"]
        try:
            if len(raw_phone) > 50:
                raise ValueError
            phone = normalize_phone(raw_phone)
        except ValueError:
            result.summary.skipped += 1
            result.report(row.number, "skipped", "The phone number is missing or unusable.")
            continue
        if raw_phone != phone:
            row.fixes.append("Normalized the phone number.")
        if phone in seen_phones:
            result.report(row.number, "notice", "Duplicate phone matched a member already seen in this file.")
        seen_phones.add(phone)

        member = db.scalar(select(Member).where(Member.phone_e164 == phone))
        if member is None:
            source_name = choice(row, "source", "source label", 100, SOURCE_ALIASES)
            if source_name is None:
                source_name = FALLBACK_SOURCE
                row.fixes.append("Used the Legacy Import source for missing or invalid attribution.")
            source = ensure_source(db, source_name)
            joined = row.date("joined_on", "join date", today)
            member = Member(
                phone_e164=phone,
                source_id=source.id,
                joined_at=datetime.combine(joined, time.min) if joined else now_utc(),
            )
            db.add(member)
            db.flush()
            ensure_personal_link(db, member)
            result.summary.created += 1
        else:
            result.summary.matched += 1

        apply_member_fields(db, member, row, today)
        legacy_id = row.text("member_id", 120, "legacy member ID")
        referrer_key = row.text("referred_by", 120, "legacy referrer ID")
        if legacy_id is None:
            result.report(row.number, "notice", "No usable legacy ID was supplied; this row cannot resolve other referrals.")
        bound.append(BoundRow(
            row.number,
            member.id,
            legacy_id.casefold() if legacy_id else None,
            referrer_key.casefold() if referrer_key else None,
        ))
        if row.fixes:
            result.summary.fixed += 1
            result.report(row.number, "fixed", " ".join(dict.fromkeys(row.fixes)))
    return bound


def register_legacy_ids(db: Session, rows: list[BoundRow], result: ImportResult) -> None:
    by_id = defaultdict(list)
    for row in rows:
        if row.legacy_id:
            by_id[row.legacy_id].append(row)

    for legacy_id, group in by_id.items():
        member_ids = {row.member_id for row in group}
        previous = db.get(LegacyMemberKey, legacy_id)
        if previous is not None:
            member_ids.add(previous.member_id)
        if len(member_ids) == 1 and None not in member_ids:
            if previous is None:
                db.add(LegacyMemberKey(legacy_id=legacy_id, member_id=group[0].member_id))
            continue
        if previous is None:
            db.add(LegacyMemberKey(legacy_id=legacy_id))
        else:
            previous.member_id = None
            referrals = list(db.scalars(
                select(Referral).join(LegacyReferralKey).where(LegacyReferralKey.legacy_id == legacy_id)
            ))
            for referral in referrals:
                referral.referrer_member_id = None
                referral.claimed_name = f"Legacy ID: {legacy_id}"[:120]
                referral.verification_status = "pending"
                referral.stage = None
                referral.participation_id = None
                referral.failure_reason = None
            if referrals:
                # Staff review becomes authoritative, so later imports must not
                # undo the decision even if another linked ID is ambiguous.
                db.execute(delete(LegacyReferralKey).where(
                    LegacyReferralKey.referral_id.in_([referral.id for referral in referrals])
                ))
                for row in group:
                    result.report(row.row, "notice", "Previously imported referrals using this ID now require staff review.")
        for row in group:
            result.report(row.row, "notice", "This legacy ID maps to multiple members; references to it were left unresolved.")
    db.flush()


def resolve_referrals(db: Session, rows: list[BoundRow], result: ImportResult) -> None:
    by_member = defaultdict(list)
    for row in rows:
        if row.referrer_key:
            by_member[row.member_id].append(row)
    for member_id, group in by_member.items():
        if db.scalar(select(Referral.id).where(Referral.referred_member_id == member_id)) is not None:
            continue
        keys = {row.referrer_key for row in group}
        references = [db.get(LegacyMemberKey, key) for key in keys]
        targets = {reference.member_id for reference in references if reference and reference.member_id}
        if len(targets) != 1 or any(reference is None or reference.member_id is None for reference in references):
            reason = "Legacy referral was not added because the referrer ID is missing, unknown, or ambiguous."
        elif member_id in targets:
            reason = "Legacy referral was not added because the member cannot refer themselves."
        else:
            referral = Referral(
                referred_member_id=member_id,
                referrer_member_id=targets.pop(),
                verification_status="verified",
                stage="lead",
            )
            db.add(referral)
            bind_referral_to_first_fit(db, referral)
            db.flush()
            db.add_all(LegacyReferralKey(referral_id=referral.id, legacy_id=key) for key in keys)
            continue
        for row in group:
            result.report(row.row, "notice", reason)


@router.post("/admin/imports/respondents")
def import_respondents(
    db: Database, _staff: CurrentStaff, file: Annotated[UploadFile, File()], preview: bool = False,
) -> ImportResult:
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise api_error(413, "csv_too_large", "Upload a CSV file of 2 MiB or less.")
    result = ImportResult(preview=preview)
    rows = parse_csv(content, result)
    lock_for_write(db)
    bound = bind_members(db, rows, result)
    register_legacy_ids(db, bound, result)
    resolve_referrals(db, bound, result)
    db.flush()
    if preview:
        db.rollback()
    else:
        db.commit()
    result.issues.sort(key=lambda issue: (issue.row, issue.action))
    return result
