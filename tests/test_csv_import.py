from datetime import date

from sqlalchemy import func, select

from app.legacy_models import LegacyMemberKey
from app.models import Interest, Member, MemberInterest, Referral, Source
from app.seed import DEMO_MEMBER_PHONE, DEMO_STAFF_EMAIL, DEMO_STAFF_PASSWORD


IMPORT_PATH = "/api/admin/imports/respondents"
HEADER = (
    "member_id,name,phone,email,gender,date_of_birth,city,income_range,interests,"
    "source,referred_by,joined_on,last_survey_completed_on\n"
)


def as_staff(make_client):
    client = make_client()
    result = client.post("/api/admin/login", json={
        "email": DEMO_STAFF_EMAIL, "password": DEMO_STAFF_PASSWORD,
    })
    assert result.status_code == 200, result.text
    return client


def upload(client, text, preview=False):
    return client.post(
        IMPORT_PATH,
        params={"preview": str(preview).lower()},
        files={"file": ("respondents.csv", text, "text/csv")},
    )


def test_csv_preview_and_commit_preserve_existing_members_and_resolve_forward_refs(make_client, session_factory):
    file_text = (
        "\ufeff" + HEADER
        + 'child,  Child Example  ,09000102202,invalid,F,15/06/1994,Bombay,10L-20L,"Tech;Health;Tech",IG,PARENT,2024-05-01,10/05/2024\n'
        + "bad-width,Ignored,9000102219\n"
        + 'parent,Parent Example,+919000102203,contact@EXAMPLE.TEST,M,17-05-94,NaviMumbai,3L-6L,"Finance;Travel",,,01/05/2024,\n'
        + "bad-phone,Ignored,not a phone,,,,,,,,,,\n"
        + "child,Overwrite Attempt,00919000102202,,,,Delhi,,,Facebook,,,2024-05-12\n"
        + f"existing,Overwrite Attempt,{DEMO_MEMBER_PHONE},,,,,3L-6L,Travel,Facebook,,,\n"
    )
    assert upload(make_client(), file_text).status_code == 401
    staff = as_staff(make_client)
    preview = upload(staff, file_text, preview=True)
    assert preview.status_code == 200, preview.text
    result = preview.json()
    assert result["preview"] is True
    assert result["summary"] == {"total": 6, "created": 2, "matched": 2, "fixed": 4, "skipped": 2}
    assert {issue["row"] for issue in result["issues"] if issue["action"] == "skipped"} == {3, 5}
    assert "Child Example" not in preview.text
    assert "9000102202" not in preview.text
    with session_factory() as session:
        assert session.get(LegacyMemberKey, "child") is None
        assert session.scalar(select(Member).where(Member.phone_e164 == "+919000102202")) is None
        assert session.scalar(select(Source).where(Source.name == "Legacy Import")) is None

    completed = upload(staff, file_text)
    assert completed.status_code == 200, completed.text
    assert completed.json() == {**result, "preview": False}

    repeated = upload(staff, file_text)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["summary"]["created"] == 0
    assert repeated.json()["summary"]["matched"] == 4
    with session_factory() as session:
        child = session.scalar(select(Member).where(Member.phone_e164 == "+919000102202"))
        parent = session.scalar(select(Member).where(Member.phone_e164 == "+919000102203"))
        existing = session.scalar(select(Member).where(Member.phone_e164 == DEMO_MEMBER_PHONE))
        assert child.name == "Child Example"
        assert child.city == "Mumbai"
        assert child.email is None
        assert child.gender == "female"
        assert child.income_range == "annual_10l_20l"
        assert child.date_of_birth == date(1994, 6, 15)
        assert child.imported_last_completed_on == date(2024, 5, 12)
        assert child.profile_completed_at is not None
        assert session.get(Source, child.source_id).name == "Instagram"
        assert session.get(Source, parent.source_id).name == "Legacy Import"
        assert parent.email == "contact@example.test"
        assert parent.city == "Navi Mumbai"
        assert existing.name == "Demo Member"
        assert existing.income_range == "under_25000"
        assert session.get(Source, existing.source_id).name == "Mumbai WhatsApp"

        interests = session.scalars(select(Interest.name).join(
            MemberInterest, Interest.id == MemberInterest.interest_id
        ).where(MemberInterest.member_id == child.id))
        assert set(interests) == {"Health & wellness", "Technology"}
        referrals = list(session.scalars(select(Referral).where(Referral.referred_member_id == child.id)))
        assert len(referrals) == 1
        assert referrals[0].referrer_member_id == parent.id
        assert referrals[0].stage == "lead"


def test_csv_never_relinks_an_ambiguous_legacy_id_on_repeat(make_client, session_factory):
    staff = as_staff(make_client)
    column_names = "member_id,name,phone,referred_by\n"
    conflicting = column_names + (
        "shared,First Example,9000102291,\n"
        "SHARED,Second Example,9000102292,\n"
        "friend,Friend Example,9000102293,Shared\n"
        "self,Self Example,9000102294,Self\n"
    )
    first = upload(staff, conflicting)
    assert first.status_code == 200, first.text
    issues = first.json()["issues"]
    assert {issue["row"] for issue in issues if issue["action"] == "notice"} == {2, 3, 4, 5}

    repeated = upload(staff, column_names + (
        "shared,First Example,9000102291,\n"
        "friend,Friend Example,9000102293,SHARED\n"
    ))
    assert repeated.status_code == 200, repeated.text
    assert any(issue["row"] == 3 and issue["action"] == "notice" for issue in repeated.json()["issues"])
    with session_factory() as session:
        assert session.get(LegacyMemberKey, "shared").member_id is None
        new_member_ids = select(Member.id).where(Member.phone_e164.in_(("+919000102293", "+919000102294")))
        count = session.scalar(select(func.count()).select_from(Referral).where(
            Referral.referred_member_id.in_(new_member_ids),
        ))
        assert count == 0


def test_later_ambiguous_id_sends_imported_referral_for_review(make_client, session_factory):
    staff = as_staff(make_client)
    columns = "member_id,name,phone,referred_by\n"
    first = upload(staff, columns + (
        "old,Original,9000102251,\n"
        "alias,Original,9000102251,\n"
        "friend,Friend,9000102252,old\n"
        "friend,Friend,9000102252,alias\n"
        "independent,Independent,9000102253,\n"
        "failed,Failed,9000102256,old\n"
    ))
    assert first.status_code == 200, first.text
    with session_factory() as session:
        original = session.scalar(select(Member).where(Member.phone_e164 == "+919000102251"))
        friend = session.scalar(select(Member).where(Member.phone_e164 == "+919000102252"))
        independent = session.scalar(select(Member).where(Member.phone_e164 == "+919000102253"))
        failed_member = session.scalar(select(Member).where(Member.phone_e164 == "+919000102256"))
        original_id = original.id
        independent_id = independent.id
        referral = session.scalar(select(Referral).where(Referral.referred_member_id == friend.id))
        referral_id = referral.id
        failed_id = session.scalar(select(Referral.id).where(Referral.referred_member_id == failed_member.id))
        assert (referral.referrer_member_id, referral.verification_status) == (original_id, "verified")
        session.add(Referral(
            referred_member_id=independent.id, referrer_member_id=original_id,
            verification_status="verified", stage="lead",
        ))
        session.commit()

    failed = staff.post(f"/api/admin/referrals/{failed_id}/fail", json={"reason": "Reviewed by staff"})
    assert failed.status_code == 204, failed.text

    collision = columns + "old,Other,9000102254,\n"
    preview = upload(staff, collision, preview=True)
    assert preview.status_code == 200, preview.text
    assert any("require staff review" in issue["reason"] for issue in preview.json()["issues"])
    with session_factory() as session:
        assert session.get(Referral, referral_id).verification_status == "verified"

    saved = upload(staff, collision)
    assert saved.status_code == 200, saved.text
    with session_factory() as session:
        referral = session.get(Referral, referral_id)
        assert (referral.referrer_member_id, referral.verification_status, referral.stage) == (None, "pending", None)
        assert referral.claimed_name == "Legacy ID: old"
        assert referral.participation_id is None
        independent_referral = session.scalar(select(Referral).where(Referral.referred_member_id == independent_id))
        assert (independent_referral.referrer_member_id, independent_referral.verification_status) == (original_id, "verified")
        failed_referral = session.get(Referral, failed_id)
        assert (failed_referral.stage, failed_referral.failure_reason) == ("failed", "Reviewed by staff")

    reviewed = staff.post(f"/api/admin/referrals/{referral_id}/review", json={"referrer_member_id": original_id})
    assert reviewed.status_code == 204, reviewed.text
    second_collision = upload(staff, columns + "alias,Another,9000102255,\n")
    assert second_collision.status_code == 200, second_collision.text
    with session_factory() as session:
        referral = session.get(Referral, referral_id)
        assert (referral.referrer_member_id, referral.verification_status) == (original_id, "verified")


def test_csv_recovers_after_broken_quoting_and_accepts_a_multiline_record(make_client, session_factory):
    staff = as_staff(make_client)
    bad = upload(staff, "name,name\nUnsupported,Header\n")
    assert bad.status_code == 422
    response = upload(staff, (
        'phone,name\n"unclosed,bad\n9000102288,"Two\nWords"\n9000102289,Next Example\n'
    ))
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["created"] == 2
    assert response.json()["summary"]["skipped"] == 1
    assert any(issue["row"] == 2 and issue["action"] == "skipped" for issue in response.json()["issues"])
    with session_factory() as session:
        multiline = session.scalar(select(Member).where(Member.phone_e164 == "+919000102288"))
        assert multiline.name == "Two Words"
