from sqlalchemy import select

from app.models import Member, Referral
from app.security import OTP_MAX_ATTEMPTS


DEMO_ADMIN = {"email": "admin@viewbox.test", "password": "ViewBoxDemo!32"}
DEMO_MEMBER_PHONE = "+919876543210"


def request_code(client, phone):
    response = client.post("/api/auth/otp/request", json={"phone": phone})
    assert response.status_code == 200, response.text
    challenge = response.json()
    return {"challenge_id": challenge["challenge_id"], "code": challenge["demo_code"]}


def verify_code(client, challenge, **attribution):
    return client.post("/api/auth/otp/verify", json={**challenge, **attribution})


def sign_in(client, phone, **attribution):
    response = verify_code(client, request_code(client, phone), **attribution)
    assert response.status_code == 200, response.text
    return response.json()


def link(client, token):
    response = client.get(f"/api/signup/links/{token}")
    assert response.status_code == 200, response.text
    return response.json()


def wrong_code_for(challenge):
    return "999999" if challenge["code"] != "999999" else "888888"


def test_tagged_signup_profile_and_logout(make_client):
    client = make_client()
    assert client.get("/api/member/me").status_code == 401

    instagram = link(client, "instagram")
    assert instagram["personal"] is False
    challenge = request_code(client, "+91 90001 02001")
    rejected = verify_code(
        client, {**challenge, "code": wrong_code_for(challenge)}, source_token="instagram",
    )
    assert rejected.status_code == 401, rejected.text
    assert client.get("/api/member/me").status_code == 401

    response = verify_code(client, challenge, source_token="instagram")
    assert response.status_code == 200, response.text
    assert "httponly" in response.headers["set-cookie"].lower()
    member = response.json()
    assert member["phone"] == "+919000102001"
    assert member["source"] == instagram["source"]
    assert member["profile_complete"] is False
    assert link(client, member["referral_token"])["personal"] is True

    replay = verify_code(make_client(), challenge, source_token="instagram")
    assert replay.status_code == 401, replay.text
    assert "set-cookie" not in replay.headers

    profile = {
        "name": "Anita Example",
        "date_of_birth": "1995-02-17",
        "gender": "Woman",
        "city": "Mumbai",
        "income_range": "₹50,000–₹99,999",
        "interests": ["Gardening", "Technology"],
    }
    future_birth_date = client.put(
        "/api/member/profile", json={**profile, "date_of_birth": "2999-01-01"},
    )
    assert future_birth_date.status_code == 422
    assert client.get("/api/member/me").json()["profile_complete"] is False

    saved = client.put("/api/member/profile", json=profile)
    assert saved.status_code == 200, saved.text
    me = client.get("/api/member/me")
    assert me.status_code == 200, me.text
    saved_member = me.json()
    assert saved_member["id"] == member["id"]
    assert saved_member["profile_complete"] is True
    for field, value in profile.items():
        if field == "interests":
            assert set(saved_member[field]) == set(value)
        else:
            assert saved_member[field] == value

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/member/me").status_code == 401


def test_otp_challenge_locks_after_repeated_wrong_codes(make_client):
    client = make_client()
    challenge = request_code(client, DEMO_MEMBER_PHONE)
    bad_challenge = {**challenge, "code": wrong_code_for(challenge)}

    for _ in range(OTP_MAX_ATTEMPTS):
        rejected = verify_code(client, bad_challenge)
        assert rejected.status_code == 401, rejected.text

    locked = verify_code(client, challenge)
    assert locked.status_code == 429, locked.text
    assert locked.json()["detail"]["code"] == "otp_attempts_exhausted"
    assert client.get("/api/member/me").status_code == 401
    assert sign_in(client, DEMO_MEMBER_PHONE)["phone"] == DEMO_MEMBER_PHONE


def test_untagged_signup_can_retry_with_a_source_and_keep_attribution(make_client):
    client = make_client()
    sources = client.get("/api/signup/sources")
    assert sources.status_code == 200, sources.text
    source = link(client, "mumbai-whatsapp")["source"]
    assert source in sources.json()

    challenge = request_code(client, "9000102002")
    missing_source = verify_code(client, challenge)
    assert missing_source.status_code == 422, missing_source.text
    assert missing_source.json()["detail"]["code"] == "source_required"
    assert client.get("/api/member/me").status_code == 401

    response = verify_code(client, challenge, source_id=source["id"])
    assert response.status_code == 200, response.text
    original = response.json()
    assert original["source"] == source

    # A fresh session signs in with a different representation of the same phone.
    existing = sign_in(make_client(), "09000102002", source_token="instagram")
    assert existing["id"] == original["id"]
    assert existing["source"] == source
    assert existing["referral_token"] == original["referral_token"]


def test_staff_can_create_a_signup_link_without_crossing_roles(make_client):
    member_client = make_client()
    sign_in(member_client, DEMO_MEMBER_PHONE)
    for path in ("/api/admin/me", "/api/admin/sources"):
        assert member_client.get(path).status_code == 401
    assert member_client.post("/api/admin/sources", json={"name": "Bypass"}).status_code == 401

    admin_client = make_client()
    login = admin_client.post("/api/admin/login", json=DEMO_ADMIN)
    assert login.status_code == 200, login.text
    assert admin_client.get("/api/admin/me").json() == {"email": DEMO_ADMIN["email"]}
    assert admin_client.get("/api/member/me").status_code == 401

    created = admin_client.post("/api/admin/sources", json={"name": "Campus Fair"})
    assert created.status_code == 201, created.text
    source = created.json()
    sources = admin_client.get("/api/admin/sources")
    assert sources.status_code == 200, sources.text
    assert source in sources.json()

    visitor = make_client()
    assert visitor.get("/api/signup/links/missing-link-token").status_code == 404
    assert link(visitor, source["token"]) == {
        "source": {"id": source["id"], "name": "Campus Fair"},
        "personal": False,
    }
    registered = sign_in(visitor, "9000102003", source_token=source["token"])
    assert registered["source"] == {"id": source["id"], "name": "Campus Fair"}


def test_link_referral_is_verified_and_name_claim_remains_pending(make_client, session_factory):
    with session_factory() as session:
        referrer = session.scalars(
            select(Member).where(Member.phone_e164 == DEMO_MEMBER_PHONE),
        ).one()
        referrer_id, referrer_name = referrer.id, referrer.name

    anonymous = make_client()
    personal = link(anonymous, "demo-member")
    assert personal["personal"] is True
    referred = sign_in(anonymous, "9000102004", source_token="demo-member")
    assert referred["source"] == personal["source"]

    claimant = make_client()
    instagram = link(claimant, "instagram")
    claimed = sign_in(
        claimant, "9000102005", source_token="instagram", referrer_name=referrer_name,
    )
    assert claimed["source"] == instagram["source"]

    with session_factory() as session:
        verified = session.scalars(
            select(Referral).where(Referral.referred_member_id == referred["id"]),
        ).one()
        assert verified.verification_status == "verified"
        assert verified.stage == "lead"
        assert verified.referrer_member_id == referrer_id

        pending = session.scalars(
            select(Referral).where(Referral.referred_member_id == claimed["id"]),
        ).one()
        assert pending.verification_status == "pending"
        assert pending.claimed_name == referrer_name
        assert pending.referrer_member_id is None
        assert pending.stage is None
