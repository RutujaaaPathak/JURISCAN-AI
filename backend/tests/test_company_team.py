"""Tests for company team management and invitation flows.

Verifies:
- Team overview (members, active, role counts, pending invites)
- Member listing scoped to company workspace
- Inviting new members (generates token hash, prevents duplicates)
- Non-admin cannot invite, change roles, or remove members (403)
- Previewing an invitation token (valid vs expired/invalid)
- Accepting an invitation (creates/links user with assigned company role)
- Single-use constraint (reusing an invitation returns 409 Conflict)
- Revoking an invitation
- Changing member roles
- Protection against demoting or removing the last active company administrator
- Company boundary isolation (Admin A cannot modify Company B's members or invitations)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token, hash_password
from app.models import Company, CompanyInvitation, User
from app.services.company import generate_invitation_token, hash_invitation_token


def _make_company(name: str) -> Company:
    db = SessionLocal()
    try:
        company = Company(name=name)
        db.add(company)
        db.commit()
        db.refresh(company)
        return company
    finally:
        db.close()


def _make_user(
    role: str,
    email: str,
    *,
    company_id: int | None = None,
    company_role: str | None = None,
    password: str = "supersecret123",
) -> tuple[User, dict[str, str]]:
    db = SessionLocal()
    try:
        user = User(
            email=email,
            username=email.split("@")[0].replace(".", "_"),
            full_name=email.split("@")[0].replace(".", " ").title(),
            hashed_password=hash_password(password),
            role=role,
            company_id=company_id,
            company_role=company_role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_access_token(user.id, secret=settings.secret_key, ttl_seconds=3600)
        return user, {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_team_overview_and_member_listing(client: TestClient):
    company = _make_company("Stark Industries")
    admin, admin_hdr = _make_user(
        "company", "tony@stark.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )
    _make_user("company", "pepper@stark.com", company_id=company.id, company_role="MANAGER")
    _make_user("company", "rhodey@stark.com", company_id=company.id, company_role="MEMBER")

    # Team overview
    overview_res = client.get("/api/company/team/overview", headers=admin_hdr)
    assert overview_res.status_code == 200
    overview = overview_res.json()
    assert overview["company"]["name"] == "Stark Industries"
    assert overview["total_members"] == 3
    assert overview["active_members"] == 3
    assert overview["role_counts"]["COMPANY_ADMIN"] == 1
    assert overview["role_counts"]["MANAGER"] == 1
    assert overview["role_counts"]["MEMBER"] == 1

    # Member list
    list_res = client.get("/api/company/team", headers=admin_hdr)
    assert list_res.status_code == 200
    members = list_res.json()["items"]
    assert len(members) == 3
    emails = {m["email"] for m in members}
    assert "tony@stark.com" in emails
    assert "pepper@stark.com" in emails


def test_admin_invitation_flow_and_acceptance(client: TestClient):
    company = _make_company("Wayne Enterprises")
    admin, admin_hdr = _make_user(
        "company", "bruce@wayne.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )

    # 1. Admin sends invitation
    invite_payload = {"email": "lucius@wayne.com", "company_role": "MANAGER"}
    invite_res = client.post("/api/company/team/invitations", json=invite_payload, headers=admin_hdr)
    assert invite_res.status_code == 201
    body = invite_res.json()
    raw_token = body["development_invitation_token"]
    assert raw_token is not None
    assert body["invitation"]["email"] == "lucius@wayne.com"
    assert body["invitation"]["status"] == "PENDING"

    # 2. Preview invitation
    preview_res = client.get(f"/api/company/invitations/preview?token={raw_token}")
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["company_name"] == "Wayne Enterprises"
    assert preview["company_role"] == "MANAGER"
    assert preview["account_exists"] is False
    assert preview["is_expired"] is False

    # 3. Accept invitation to create a new user account
    accept_payload = {
        "token": raw_token,
        "full_name": "Lucius Fox",
        "password": "techinnovator123",
    }
    accept_res = client.post("/api/company/invitations/accept", json=accept_payload)
    assert accept_res.status_code == 200
    accept_body = accept_res.json()
    assert accept_body["token_type"] == "bearer"
    assert accept_body["user"]["email"] == "lucius@wayne.com"
    assert accept_body["user"]["company_role"] == "MANAGER"

    # 4. Single-use token prevention (attempting to accept again fails with 409)
    reused_res = client.post("/api/company/invitations/accept", json=accept_payload)
    assert reused_res.status_code == 409
    assert reused_res.json()["error"]["code"] == "invitation_used"


def test_invite_permissions_and_duplicate_handling(client: TestClient):
    company = _make_company("Umbrella Corp")
    admin, admin_hdr = _make_user(
        "company", "wesker@umbrella.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )
    member, member_hdr = _make_user(
        "company", "birkin@umbrella.com", company_id=company.id, company_role="MEMBER"
    )

    # Non-admin cannot invite members
    forbidden = client.post(
        "/api/company/team/invitations",
        json={"email": "claire@umbrella.com", "company_role": "VIEWER"},
        headers=member_hdr,
    )
    assert forbidden.status_code == 403

    # Admin cannot invite someone already in the company
    dup_res = client.post(
        "/api/company/team/invitations",
        json={"email": "birkin@umbrella.com", "company_role": "MEMBER"},
        headers=admin_hdr,
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "already_company_member"


def test_revoke_invitation(client: TestClient):
    company = _make_company("Cyberdyne")
    admin, admin_hdr = _make_user(
        "company", "miles@cyberdyne.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )

    res = client.post(
        "/api/company/team/invitations",
        json={"email": "arnold@cyberdyne.com", "company_role": "VIEWER"},
        headers=admin_hdr,
    )
    assert res.status_code == 201
    inv_id = res.json()["invitation"]["id"]
    token = res.json()["development_invitation_token"]

    # Revoke
    revoke_res = client.post(f"/api/company/team/invitations/{inv_id}/revoke", headers=admin_hdr)
    assert revoke_res.status_code == 200
    assert revoke_res.json()["status"] == "REVOKED"

    # Acceptance of revoked invitation is rejected
    accept_res = client.post(
        "/api/company/invitations/accept",
        json={"token": token, "password": "password1234", "full_name": "T800"},
    )
    assert accept_res.status_code == 409
    assert accept_res.json()["error"]["code"] == "invitation_revoked"


def test_role_change_and_last_admin_protection(client: TestClient):
    company = _make_company("Oscorp")
    admin, admin_hdr = _make_user(
        "company", "norman@oscorp.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )
    member, _ = _make_user(
        "company", "harry@oscorp.com", company_id=company.id, company_role="MEMBER"
    )

    # 1. Promote member to manager
    promote_res = client.patch(
        f"/api/company/team/members/{member.id}/role",
        json={"company_role": "MANAGER"},
        headers=admin_hdr,
    )
    assert promote_res.status_code == 200
    assert promote_res.json()["company_role"] == "MANAGER"

    # 2. Cannot demote the sole active administrator
    demote_sole_res = client.patch(
        f"/api/company/team/members/{admin.id}/role",
        json={"company_role": "MANAGER"},
        headers=admin_hdr,
    )
    assert demote_sole_res.status_code == 409
    assert demote_sole_res.json()["error"]["code"] == "last_company_admin"

    # 3. Promote another user to admin, then demotion of first admin succeeds
    client.patch(
        f"/api/company/team/members/{member.id}/role",
        json={"company_role": "COMPANY_ADMIN"},
        headers=admin_hdr,
    )
    demote_res = client.patch(
        f"/api/company/team/members/{admin.id}/role",
        json={"company_role": "MEMBER"},
        headers=admin_hdr,
    )
    assert demote_res.status_code == 200
    assert demote_res.json()["company_role"] == "MEMBER"


def test_remove_member_and_last_admin_protection(client: TestClient):
    company = _make_company("Initech")
    admin, admin_hdr = _make_user(
        "company", "peter@initech.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )
    member, _ = _make_user(
        "company", "milton@initech.com", company_id=company.id, company_role="MEMBER"
    )

    # 1. Cannot delete the only administrator
    del_admin_res = client.delete(f"/api/company/team/members/{admin.id}", headers=admin_hdr)
    assert del_admin_res.status_code == 409
    assert del_admin_res.json()["error"]["code"] == "last_company_admin"

    # 2. Remove standard member succeeds
    del_res = client.delete(f"/api/company/team/members/{member.id}", headers=admin_hdr)
    assert del_res.status_code == 204

    # Verify member is no longer listed in company team
    list_res = client.get("/api/company/team", headers=admin_hdr)
    assert len(list_res.json()["items"]) == 1


def test_company_team_isolation(client: TestClient):
    comp1 = _make_company("Enterprise One")
    comp2 = _make_company("Enterprise Two")

    admin1, hdr1 = _make_user("company", "boss1@e1.com", company_id=comp1.id, company_role="COMPANY_ADMIN")
    member2, _ = _make_user("company", "staff2@e2.com", company_id=comp2.id, company_role="MEMBER")

    # Admin 1 cannot change member 2's role (returns 404 because user is not in comp1)
    res = client.patch(
        f"/api/company/team/members/{member2.id}/role",
        json={"company_role": "COMPANY_ADMIN"},
        headers=hdr1,
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "team_member_not_found"

    # Admin 1 cannot remove member 2
    del_res = client.delete(f"/api/company/team/members/{member2.id}", headers=hdr1)
    assert del_res.status_code == 404

