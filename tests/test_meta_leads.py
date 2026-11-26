from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.meta_models import MetaLead
from app.models import Member, SignupLink, Source


ENDPOINT = "/api/integrations/meta/leads"
DEMO_ADMIN = {"email": "admin@viewbox.test", "password": "ViewBoxDemo!32"}


def lead_record(
    lead_id="lead-1001",
    phone="098123 45001",
    name="Neha Sharma",
    city="Mumbai",
    email="neha@example.test",
):
    fields = [
        {"name": "full_name", "values": [name]},
        {"name": "phone_number", "values": [phone]},
        {"name": "city", "values": [city]},
        {"name": "interests", "values": ["Food", "Shopping"]},
    ]
    if email is not None:
        fields.append({"name": "email", "values": [email]})
    return {
        "id": lead_id,
        "form_id": "form-110",
        "campaign_id": "campaign-120",
        "ad_id": "ad-130",
        "created_time": "2026-11-21T14:00:00+0530",
        "field_data": fields,
    }


def sign_in_admin(client):
    response = client.post("/api/admin/login", json=DEMO_ADMIN)
    assert response.status_code == 200, response.text
    return client


@pytest.fixture
def admin_client(make_client):
    return sign_in_admin(make_client())


def test_meta_intake_creates_member_and_replays_original_record(admin_client, session_factory):
    response = admin_client.post(ENDPOINT, json=lead_record())
    assert response.status_code == 201, response.text
    original = response.json()
    assert original == {
        "lead_id": "lead-1001",
        "member_id": original["member_id"],
        "campaign_id": "campaign-120",
        "created_member": True,
        "duplicate": False,
    }

    changed = lead_record(phone="+919812345002", city="Delhi")
    changed["campaign_id"] = "other-campaign"
    repeated = admin_client.post(ENDPOINT, json=changed)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json() == {**original, "duplicate": True}

    with session_factory() as db:
        member = db.get(Member, original["member_id"])
        assert member.phone_e164 == "+919812345001"
        assert (member.name, member.email, member.city) == ("Neha Sharma", "neha@example.test", "Mumbai")
        assert member.profile_completed_at is None
        assert db.get(Source, member.source_id).name == "Meta Ads"
        assert db.scalar(select(SignupLink.id).where(SignupLink.owner_member_id == member.id))
        assert db.scalar(select(Member.id).where(Member.phone_e164 == "+919812345002")) is None

        saved = db.get(MetaLead, original["lead_id"])
        assert (saved.form_id, saved.ad_id) == ("form-110", "ad-130")
        assert saved.submitted_at == datetime(2026, 11, 21, 8, 30)
        assert db.scalar(select(func.count()).select_from(MetaLead)) == 1


def test_meta_intake_matches_existing_member_and_keeps_attribution(admin_client, session_factory):
    payload = lead_record(phone="+91 98765-43210", name="Do Not Replace", city="Delhi")
    del payload["ad_id"]
    response = admin_client.post(ENDPOINT, json=payload)
    assert response.status_code == 201, response.text
    matched = response.json()
    assert matched["created_member"] is False

    payload = lead_record(
        lead_id="lead-1002", phone="9876543210", city="Pune", email="replacement@example.test"
    )
    second = admin_client.post(ENDPOINT, json=payload)
    assert second.status_code == 201, second.text
    assert second.json()["member_id"] == matched["member_id"]
    assert second.json()["created_member"] is False

    with session_factory() as db:
        member = db.get(Member, matched["member_id"])
        assert db.get(Source, member.source_id).name == "Mumbai WhatsApp"
        assert (member.name, member.city, member.email) == ("Demo Member", "Mumbai", "neha@example.test")
        assert member.profile_completed_at is not None
        assert db.get(MetaLead, matched["lead_id"]).ad_id is None
        assert db.scalar(select(func.count()).select_from(MetaLead)) == 2
        assert db.scalar(select(Source.id).where(Source.name == "Meta Ads")) is None


def test_meta_intake_requires_an_admin_session(make_client, session_factory):
    anonymous = make_client()
    assert anonymous.post(ENDPOINT, json=lead_record()).status_code == 401
    staff = make_client()
    login = staff.post(
        "/api/admin/login", json={"email": "staff@viewbox.test", "password": "ViewBoxStaff!32"},
    )
    assert login.status_code == 200, login.text
    assert staff.post(ENDPOINT, json=lead_record()).status_code == 403
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(MetaLead)) == 0


def test_invalid_meta_records_do_not_create_members(admin_client, session_factory):
    missing_campaign = lead_record()
    del missing_campaign["campaign_id"]
    missing_city = lead_record()
    missing_city["field_data"] = [field for field in missing_city["field_data"] if field["name"] != "city"]
    duplicate_city = lead_record()
    duplicate_city["field_data"].append({"name": " CITY ", "values": ["Pune"]})
    ambiguous_name = lead_record()
    ambiguous_name["field_data"][0]["values"].append("Another Name")

    for record in (
        {**lead_record(), "id": " "},
        missing_campaign,
        {**lead_record(), "created_time": "2026-11-21T14:00:00"},
        missing_city,
        duplicate_city,
        ambiguous_name,
        lead_record(phone="invalid"),
        lead_record(email="name@bad..test"),
    ):
        response = admin_client.post(ENDPOINT, json=record)
        assert response.status_code == 422, response.text
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(MetaLead)) == 0
        assert db.scalar(select(Member.id).where(Member.phone_e164 == "+919812345001")) is None
        assert db.scalar(select(Source.id).where(Source.name == "Meta Ads")) is None


def test_racing_deliveries_create_one_lead_and_one_member(make_client, session_factory):
    admins = [sign_in_admin(make_client()), sign_in_admin(make_client())]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(
            lambda client: client.post(ENDPOINT, json=lead_record(email=None)), admins,
        ))

    assert sorted([first.status_code, second.status_code]) == [200, 201]
    assert first.json()["member_id"] == second.json()["member_id"]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(MetaLead)) == 1
        assert db.scalar(
            select(func.count()).select_from(Member).where(Member.phone_e164 == "+919812345001")
        ) == 1
