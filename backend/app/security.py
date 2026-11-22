import hashlib
import hmac
import os
import re
from datetime import UTC, datetime
from secrets import token_hex

from fastapi import HTTPException, Response
from sqlalchemy.orm import Session

from .models import LoginSession

MEMBER_COOKIE = "viewbox_member"
ADMIN_COOKIE = "viewbox_admin"
DEMO_OTP = "123456"
OTP_MAX_ATTEMPTS = 5


def now_utc() -> datetime:
    # SQLite stores these timestamps without an offset. Treat them as UTC.
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_phone(phone: str) -> str:
    if not re.fullmatch(r"[0-9+().\-\s]+", phone):
        raise ValueError("Enter a valid phone number.")
    digits = re.sub(r"[().\-\s]", "", phone)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if re.fullmatch(r"0?[1-9][0-9]{9}", digits):
        digits = "+91" + digits[-10:]
    elif re.fullmatch(r"91[1-9][0-9]{9}", digits):
        digits = "+" + digits
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", digits):
        raise ValueError("Enter a 10-digit Indian number or include the country code.")
    if digits.startswith("+91") and not re.fullmatch(r"\+91[1-9][0-9]{9}", digits):
        raise ValueError("Enter 10 digits after India’s +91 calling code.")
    return digits


def hash_password(password: str, salt: str | None = None) -> str:
    salt = token_hex(16) if salt is None else salt
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024
    )
    return salt + "$" + digest.hex()


def password_matches(password: str, password_hash: str) -> bool:
    salt, _ = password_hash.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def set_session_cookie(response: Response, cookie: str, token: str, max_age: int) -> None:
    response.set_cookie(
        cookie,
        token,
        max_age=max_age,
        path="/api",
        httponly=True,
        secure=os.getenv("VIEWBOX_SECURE_COOKIES") == "1",
        samesite="lax",
    )


def find_session(db: Session, token: str | None) -> LoginSession | None:
    if not token:
        return None
    login = db.get(LoginSession, hash_token(token))
    return login if login and login.expires_at > now_utc() else None


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, detail={"code": code, "message": message})
