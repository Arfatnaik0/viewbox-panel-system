from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from .db import get_db
from .models import Member, StaffAccount
from .security import ADMIN_COOKIE, MEMBER_COOKIE, api_error, find_session

Database = Annotated[Session, Depends(get_db)]
MemberToken = Annotated[str | None, Cookie(alias=MEMBER_COOKIE)]
AdminToken = Annotated[str | None, Cookie(alias=ADMIN_COOKIE)]
STAFF_ROLES = ("staff", "admin")


def require_member(db: Database, token: MemberToken = None) -> Member:
    login = find_session(db, token)
    if login and login.member_id is not None:
        member = db.get(Member, login.member_id)
        if member and member.status == "active":
            return member
    raise api_error(401, "member_login_required", "Sign in to your member account.")


def require_staff(db: Database, token: AdminToken = None) -> StaffAccount:
    login = find_session(db, token)
    if login and login.staff_id is not None:
        staff = db.get(StaffAccount, login.staff_id)
        if staff and staff.role in STAFF_ROLES:
            return staff
    raise api_error(401, "staff_login_required", "Sign in to your staff account.")


CurrentMember = Annotated[Member, Depends(require_member)]
CurrentStaff = Annotated[StaffAccount, Depends(require_staff)]


def require_admin(staff: CurrentStaff) -> StaffAccount:
    if staff.role != "admin":
        raise api_error(403, "admin_required", "This action requires an admin account.")
    return staff


CurrentAdmin = Annotated[StaffAccount, Depends(require_admin)]
