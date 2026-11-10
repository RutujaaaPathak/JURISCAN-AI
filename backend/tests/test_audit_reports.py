from __future__ import annotations

import io
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models import Analysis, Clause, Company, Document, RiskFinding, User


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
) -> tuple[User, dict[str, str]]:
    db = SessionLocal()
    try:
        user = User(
            email=email,
            username=email.split("@")[0],
            full_name=email.split("@")[0].title(),
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


def _make_document_with_analysis(
    user_id: int,
    company_id: int | None,
    title: str,
    *,
    risk_score: float = 60.0,
    status: str = "PROCESSED",
    analysis_status: str = "COMPLETED",
    error_message: str | None = None,
    days_ago: int = 0,
) -> Document:
    db = SessionLocal()
    try:
        created_dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
        doc = Document(
            user_id=user_id,
            company_id=company_id,
            title=title,
            filename=f"{title.lower().replace(' ', '_')}.pdf",
            file_type="pdf",
            status=status,
            page_count=2,
            word_count=500,
            text_content="1. Confidentiality\nConfidential forever.",
            extracted_at=created_dt,
            error_message=error_message,
        )
        db.add(doc)
        db.flush()

        if status == "PROCESSED":
            clause = Clause(
                document_id=doc.id,
                clause_number=1,
                heading="Confidentiality",
                text="Confidential forever without limitation.",
                page_number=1,
            )
            db.add(clause)
            db.flush()

            analysis = Analysis(
                document_id=doc.id,
                model_name="juriscan-rules-v1",
                status=analysis_status,
                risk_score=risk_score,
                summary="Test analysis summary with flagged provisions.",
                completed_at=created_dt,
            )
            db.add(analysis)
            db.flush()

            finding = RiskFinding(
                analysis_id=analysis.id,
                clause_id=clause.id,
                rule_code="CONF_PERPETUAL",
                severity="HIGH" if risk_score >= 50 else "LOW",
                title="Perpetual Confidentiality Obligation",
                description="The obligation has no end date.",
                recommendation="Limit confidentiality duration to 3-5 years.",
                citation="Section 27, Indian Contract Act, 1872",
            )
            db.add(finding)

        db.commit()
        db.refresh(doc)
        return doc
    finally:
        db.close()


def test_audit_overview_metrics(client: TestClient):
    company = _make_company("Acme Enterprise")
    user, headers = _make_user(
        "company", "admin@acme-ent.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )

    # 1. Empty state
    res = client.get("/api/company/audit-reports/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_reports"] == 0
    assert data["ready_reports"] == 0
    assert data["high_risk_reports"] == 0

    # 2. Add high risk document (score 65 -> HIGH)
    _make_document_with_analysis(user.id, company.id, "Vendor Agreement", risk_score=65.0)
    # Add low risk document (score 15 -> LOW)
    _make_document_with_analysis(user.id, company.id, "NDA Agreement", risk_score=15.0)

    res = client.get("/api/company/audit-reports/overview", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_reports"] == 2
    assert data["ready_reports"] == 2
    assert data["high_risk_reports"] == 1
    assert data["low_risk_reports"] == 1
    assert data["avg_risk_score"] == 40.0
    assert len(data["recent_activity"]) == 2


def test_list_audit_reports_and_filtering(client: TestClient):
    company = _make_company("Beta Logistics")
    user, headers = _make_user(
        "company", "ops@beta.com", company_id=company.id, company_role="MEMBER"
    )

    doc1 = _make_document_with_analysis(user.id, company.id, "Master Services Agreement", risk_score=75.0)
    doc2 = _make_document_with_analysis(user.id, company.id, "Consulting Contract", risk_score=20.0)

    # List all
    res = client.get("/api/company/audit-reports", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2

    # Filter by search
    res = client.get("/api/company/audit-reports?q=Consulting", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["document_id"] == doc2.id

    # Filter by risk level
    res = client.get("/api/company/audit-reports?risk_level=CRITICAL", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["document_id"] == doc1.id

    res = client.get("/api/company/audit-reports?risk_level=LOW", headers=headers)
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["document_id"] == doc2.id


def test_audit_report_detail_and_pdf_download(client: TestClient):
    company = _make_company("Gamma Pharma")
    user, headers = _make_user(
        "company", "counsel@gamma.com", company_id=company.id, company_role="MANAGER"
    )

    doc = _make_document_with_analysis(user.id, company.id, "Supply Contract", risk_score=55.0)

    # Get detail
    res = client.get(f"/api/company/audit-reports/{doc.id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["document_id"] == doc.id
    assert data["document_title"] == "Supply Contract"
    assert data["model_name"] == "juriscan-rules-v1"
    assert len(data["findings"]) == 1
    assert data["findings"][0]["rule_code"] == "CONF_PERPETUAL"
    assert data["findings"][0]["citation"] == "Section 27, Indian Contract Act, 1872"
    assert data["findings"][0]["recommendation"] is not None

    # Download PDF report
    pdf_res = client.get(f"/api/company/audit-reports/{doc.id}/report", headers=headers)
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert f'filename="juriscan-audit-{doc.id}.pdf"' in pdf_res.headers["content-disposition"]
    assert pdf_res.content.startswith(b"%PDF")


def test_company_isolation_and_unauthorized_access(client: TestClient):
    company_a = _make_company("Company A")
    company_b = _make_company("Company B")

    user_a, headers_a = _make_user(
        "company", "alice@company-a.com", company_id=company_a.id, company_role="MEMBER"
    )
    user_b, headers_b = _make_user(
        "company", "bob@company-b.com", company_id=company_b.id, company_role="MEMBER"
    )
    individual_user, headers_ind = _make_user("individual", "charlie@client.com")

    # Document belongs to Company A
    doc_a = _make_document_with_analysis(user_a.id, company_a.id, "Secret Deal A", risk_score=80.0)

    # User B from Company B receives 404 when querying Company A's report
    detail_res = client.get(f"/api/company/audit-reports/{doc_a.id}", headers=headers_b)
    assert detail_res.status_code == 404

    pdf_res = client.get(f"/api/company/audit-reports/{doc_a.id}/report", headers=headers_b)
    assert pdf_res.status_code == 404

    # User B cannot see Company A's report in list
    list_res = client.get("/api/company/audit-reports", headers=headers_b)
    assert list_res.status_code == 200
    assert list_res.json()["total"] == 0

    # Non-company account receives 403 Forbidden
    forbidden_res = client.get("/api/company/audit-reports", headers=headers_ind)
    assert forbidden_res.status_code == 403


def test_company_upload_contract_automatically_appears_in_audit_reports(client: TestClient):
    company = _make_company("Delta Corp")
    user, headers = _make_user(
        "company", "lead@deltacorp.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )

    # 1. Company uploads a contract through the API
    contract_text = (
        b"1. Scope of Services\nVendor provides cloud consulting services.\n\n"
        b"2. Liability\nVendor liability shall be completely uncapped for all claims.\n\n"
        b"3. Termination\nCustomer may terminate at will upon ten days notice.\n"
    )
    upload_res = client.post(
        "/api/documents",
        headers=headers,
        files={"file": ("delta_cloud_contract.txt", contract_text, "text/plain")},
        data={"title": "Delta Cloud Agreement"},
    )
    assert upload_res.status_code == 201, upload_res.text
    uploaded_doc = upload_res.json()
    assert uploaded_doc["status"] == "PROCESSED"
    assert uploaded_doc["risk_level"] is not None

    # 2. Verify it appears automatically in Audit Reports
    audit_res = client.get("/api/company/audit-reports", headers=headers)
    assert audit_res.status_code == 200
    reports = audit_res.json()
    assert reports["total"] == 1
    item = reports["items"][0]
    assert item["document_id"] == uploaded_doc["id"]
    assert item["document_title"] == "Delta Cloud Agreement"
    assert item["report_status"] == "READY"
    assert item["risk_level"] == uploaded_doc["risk_level"]
    assert item["finding_count"] == uploaded_doc["finding_count"]

    # 3. Verify overview stats reflect this contract
    overview_res = client.get("/api/company/audit-reports/overview", headers=headers)
    assert overview_res.status_code == 200
    overview = overview_res.json()
    assert overview["total_reports"] == 1
    assert overview["ready_reports"] == 1
    assert overview["avg_risk_score"] == uploaded_doc["risk_score"]


def test_existing_unassigned_document_automatically_linked_to_company(client: TestClient):
    company = _make_company("Epsilon Tech")
    user, headers = _make_user(
        "company", "cto@epsilon.com", company_id=company.id, company_role="COMPANY_ADMIN"
    )

    # Create an unassigned document (uploaded by user earlier without company_id)
    doc = _make_document_with_analysis(user.id, None, "Early Startup NDA", risk_score=70.0)

    # When the company lists audit reports, the document appears and is backfilled
    res = client.get("/api/company/audit-reports", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["document_id"] == doc.id
    assert data["items"][0]["document_title"] == "Early Startup NDA"

    # Verify document now has company_id persisted in DB
    db = SessionLocal()
    try:
        refreshed = db.get(Document, doc.id)
        assert refreshed.company_id == company.id
    finally:
        db.close()


def test_failed_and_processing_documents_in_audit_reports(client: TestClient):
    company = _make_company("Zeta Media")
    user, headers = _make_user(
        "company", "editor@zeta.com", company_id=company.id, company_role="MANAGER"
    )

    # 1. Add completed document
    _make_document_with_analysis(user.id, company.id, "Valid Agreement", risk_score=30.0)

    # 2. Add failed document
    failed_doc = _make_document_with_analysis(
        user.id,
        company.id,
        "Corrupted Agreement",
        status="FAILED",
        analysis_status="FAILED",
        error_message="Document text extraction failed due to encryption.",
    )

    # 3. Add processing document
    processing_doc = _make_document_with_analysis(
        user.id,
        company.id,
        "In Flight Contract",
        status="PROCESSING",
        analysis_status="PENDING",
    )

    # Overview
    overview_res = client.get("/api/company/audit-reports/overview", headers=headers)
    assert overview_res.status_code == 200
    ov = overview_res.json()
    assert ov["total_reports"] == 3
    assert ov["ready_reports"] == 1
    assert ov["failed_reports"] == 1
    assert ov["requiring_attention"] >= 1  # includes failed
    # Average score only includes valid completed results (30.0)
    assert ov["avg_risk_score"] == 30.0

    # List reports and check statuses
    list_res = client.get("/api/company/audit-reports", headers=headers)
    assert list_res.status_code == 200
    items = {item["document_id"]: item for item in list_res.json()["items"]}
    assert items[failed_doc.id]["report_status"] == "FAILED"
    assert items[failed_doc.id]["error_message"] == "Document text extraction failed due to encryption."
    assert items[processing_doc.id]["report_status"] == "PENDING"

    # Filter by status: FAILED
    failed_res = client.get("/api/company/audit-reports?report_status=FAILED", headers=headers)
    assert failed_res.status_code == 200
    assert failed_res.json()["total"] == 1
    assert failed_res.json()["items"][0]["document_id"] == failed_doc.id

    # Filter by status: COMPLETED or READY
    completed_res = client.get("/api/company/audit-reports?report_status=COMPLETED", headers=headers)
    assert completed_res.status_code == 200
    assert completed_res.json()["total"] == 1

    # Filter by status: PROCESSING or PENDING
    proc_res = client.get("/api/company/audit-reports?report_status=PROCESSING", headers=headers)
    assert proc_res.status_code == 200
    assert proc_res.json()["total"] == 1
    assert proc_res.json()["items"][0]["document_id"] == processing_doc.id
