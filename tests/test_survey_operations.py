import csv
from datetime import UTC, datetime, timedelta
from io import StringIO

from app.seed import DEMO_REFERRED_PHONE
from test_panel_flows import DEMO_ADMIN, DEMO_MEMBER_PHONE, sign_in

DEMO_STAFF = {"email": "staff@viewbox.test", "password": "ViewBoxStaff!32"}


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def staff_client(make_client, credentials):
    client = make_client()
    ok(client.post("/api/admin/login", json=credentials))
    return client


def survey_payload(**overrides):
    now = datetime.now(UTC)
    return {
        "title": "Shopping study",
        "description": "A short study on shopping habits.",
        "opens_at": (now - timedelta(days=1)).isoformat(),
        "closes_at": (now + timedelta(days=7)).isoformat(),
        "quota": 3,
        "published": True,
        "interests": ["Shopping"],
        "rules": [],
        **overrides,
    }


def create_survey(admin, **overrides):
    return ok(admin.post("/api/admin/surveys", json=survey_payload(**overrides)), 201)


def apply(client, survey_id):
    return ok(client.post(f"/api/member/surveys/{survey_id}/apply"))


def test_publish_preview_and_quota_are_separate(make_client):
    admin = staff_client(make_client, DEMO_ADMIN)
    member, referred = make_client(), make_client()
    sign_in(member, DEMO_MEMBER_PHONE)
    sign_in(referred, DEMO_REFERRED_PHONE)

    invalid = survey_payload(closes_at=(datetime.now(UTC) + timedelta(days=16)).isoformat())
    assert admin.post("/api/admin/surveys", json=invalid).status_code == 422
    survey_id = create_survey(admin, quota=1, published=False)["id"]
    assert survey_id not in {item["id"] for item in ok(member.get("/api/member/surveys"))}
    ok(admin.patch(f"/api/admin/surveys/{survey_id}/publish", json={"published": True}))

    for client in (member, referred):
        preview = ok(client.get(f"/api/member/surveys/{survey_id}"))
        assert preview["interest_match"] is True
        assert preview["eligibility"]["status"] == "approved"
        assert preview["participation"] is None

    approved = apply(member, survey_id)
    assert approved["participation"]["eligibility_status"] == "approved"
    assert apply(member, survey_id)["participation"]["id"] == approved["participation"]["id"]
    rejected = apply(referred, survey_id)
    assert rejected["eligibility"]["status"] == "rejected"
    assert rejected["participation"] is None
    assert rejected["eligibility"]["reason"]


def test_scheduled_survey_is_hidden_from_members(make_client):
    admin = staff_client(make_client, DEMO_ADMIN)
    member = make_client()
    sign_in(member, DEMO_MEMBER_PHONE)

    opens = datetime.now(UTC) + timedelta(days=1)
    survey = create_survey(admin, opens_at=opens.isoformat())
    path = f"/api/member/surveys/{survey['id']}"
    assert member.get(path).status_code == 404
    assert member.post(f"{path}/apply").status_code == 404


def test_strict_failure_takes_priority_over_waitlist(make_client):
    admin = staff_client(make_client, DEMO_ADMIN)
    member = make_client()
    sign_in(member, DEMO_MEMBER_PHONE)
    flexible = {"field": "city", "mode": "flexible", "values": ["Pune"]}
    waitlist_id = create_survey(admin, title="Flexible city study", rules=[flexible])["id"]
    result = apply(member, waitlist_id)
    assert result["participation"]["eligibility_status"] == "waitlisted"
    assert result["eligibility"]["reason"]

    strict_age = {"field": "age", "mode": "strict", "values": [18, 19]}
    strict_gender = {"field": "gender", "mode": "strict", "values": ["male"]}
    strict_id = create_survey(admin, rules=[flexible, strict_age, strict_gender])["id"]
    result = apply(member, strict_id)
    assert result["eligibility"]["status"] == "rejected"
    assert result["participation"] is None
    reason = result["eligibility"]["reason"]
    assert "ages 18 to 19" in reason
    assert "genders: male" in reason
    assert "Pune" not in reason


def test_staff_milestones_update_referrer_and_cool_off(make_client):
    admin = staff_client(make_client, DEMO_ADMIN)
    staff = staff_client(make_client, DEMO_STAFF)
    assert ok(staff.get("/api/admin/session"))["role"] == "staff"
    assert staff.post("/api/admin/surveys", json=survey_payload()).status_code == 403
    assert staff.get("/api/admin/sources").status_code == 403

    member, referrer = make_client(), make_client()
    referred = sign_in(member, DEMO_REFERRED_PHONE)
    sign_in(referrer, DEMO_MEMBER_PHONE)
    other = make_client()
    sign_in(other, DEMO_REFERRED_PHONE)
    assert ok(other.get("/api/member/referrals")) == []
    [lead] = ok(referrer.get("/api/member/referrals"))
    assert lead["stage"] == "lead"
    assert "X" in lead["phone_masked"].upper()
    assert DEMO_REFERRED_PHONE not in str(lead)

    age_rule = {"field": "age", "mode": "strict", "values": [18, 65]}
    city_rule = {"field": "city", "mode": "strict", "values": ["Pune"]}
    first = create_survey(admin, title="First study", rules=[age_rule])["id"]
    second = create_survey(admin, title="Second study", rules=[city_rule])["id"]
    participation = apply(member, first)["participation"]["id"]
    path = f"/api/admin/participations/{participation}"
    assert staff.post(f"{path}/complete").status_code in (409, 422)
    ok(staff.post(f"{path}/fit"), 204)
    assert ok(referrer.get("/api/member/referrals"))[0]["stage"] == "fit"
    ok(staff.post(f"{path}/complete"), 204)
    assert ok(referrer.get("/api/member/referrals"))[0]["stage"] == "completed"
    details = ok(staff.get(f"/api/admin/respondents/{referred['id']}"))
    for field in ("date_of_birth", "gender", "income_range"):
        assert details[field] == referred[field]
    [completed] = details["participations"]
    assert completed["rules"] == [age_rule]
    assert completed["eligibility_reason"] == "Your profile meets the survey requirements."
    assert datetime.fromisoformat(completed["completed_at"]).utcoffset() == timedelta(0)

    blocked = apply(member, second)
    assert blocked["participation"] is None
    assert blocked["eligibility"]["status"] == "rejected"
    assert "cool-off" in blocked["eligibility"]["reason"]
    assert "Pune" in blocked["eligibility"]["reason"]
    assert blocked["eligibility"]["eligible_on"] > datetime.now(UTC).date().isoformat()
    stats = {item["id"]: item for item in ok(staff.get("/api/admin/source-stats"))}
    assert stats[referred["source"]["id"]]["completed"] == 1
    assert stats[referred["source"]["id"]]["fit"] == 1


def test_named_referral_review_and_filtered_csv(make_client):
    staff = staff_client(make_client, DEMO_STAFF)
    referrer, claimant = make_client(), make_client()
    owner = sign_in(referrer, DEMO_MEMBER_PHONE)
    new_member = sign_in(claimant, "9000102045", source_token="instagram", referrer_name=owner["name"])
    ok(claimant.put("/api/member/profile", json={
        "name": "=Test Respondent", "date_of_birth": "1994-06-01", "gender": "female",
        "city": "Pune", "income_range": "under_25000", "interests": ["Travel"],
    }))
    detail = ok(staff.get(f"/api/admin/respondents/{new_member['id']}"))
    assert detail["referral"]["verification_status"] == "pending"
    claim_path = f"/api/admin/referrals/{detail['referral']['id']}"
    ok(staff.post(f"{claim_path}/review", json={"referrer_member_id": owner["id"]}), 204)
    ok(staff.post(f"{claim_path}/fail", json={"reason": "Survey participation was incomplete."}), 204)
    referrals = ok(referrer.get("/api/member/referrals"))
    failed = next(row for row in referrals if row["stage"] == "failed")
    assert failed["failure_reason"] == "Survey participation was incomplete."

    filters = {"search": "Respondent", "city": "pune", "source_id": new_member["source"]["id"]}
    result = ok(staff.get("/api/admin/respondents", params=filters))
    assert [row["id"] for row in result["respondents"]] == [new_member["id"]]
    exported = staff.get("/api/admin/respondents/export", params=filters)
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    header, row = list(csv.reader(StringIO(exported.text.lstrip("\ufeff"))))
    assert len(header) == len(row)
    assert str(new_member["id"]) in row
    assert "'=Test Respondent" in row
