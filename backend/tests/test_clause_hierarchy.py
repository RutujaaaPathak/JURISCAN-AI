"""Comprehensive tests for clause hierarchy and persistence.

Covers:
- Hierarchy and metadata persistence (label, level, parent_id, start_offset, end_offset)
- Within-document parent-child hierarchy and ORM relationships (parent, children)
- Cross-document parent protection (raises ValueError)
- Self-parent cycle protection (raises ValueError)
- ID reuse and risk-finding reference preservation across retries/reprocessing
- Prevention of duplicate clauses during retries
- Preservation of original wording, source offsets, page numbers, and clause order
- Support and backfill for legacy clause records
- API serialization and detail payload exposure
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Analysis, Clause, Document, RiskFinding, User
from app.schemas.documents import ClauseRead, RiskFindingRead
from app.services.processing import (
    persist_clauses,
    process_upload,
    run_processing,
    sync_legacy_clause_hierarchy,
)
from app.services.segmentation import segment_clauses
from tests.pdf_factory import multi_page_pdf


SAMPLE_HIERARCHICAL_CONTRACT = """1. Definitions
In this Agreement the following terms have the meanings given.

2. Obligations
2.1 The Supplier shall provide the Services with reasonable skill and care.
2.2 The Customer shall pay the fees within thirty (30) days of invoice.
(a) Late payments shall accrue interest at the agreed contractual rate.
(b) Disputed amounts may be withheld pending resolution.

3. Termination
3.1 Either party may terminate for material breach on thirty (30) days notice.
"""


def _create_user(session: Session, email: str = "hierarchy@example.com") -> User:
    user = User(email=email, username=email.split("@")[0], full_name="Hierarchy User")
    session.add(user)
    session.flush()
    return user


def _create_doc(
    session: Session,
    user: User,
    title: str = "Hierarchical Agreement",
    text: str = SAMPLE_HIERARCHICAL_CONTRACT,
) -> Document:
    doc = Document(
        user_id=user.id,
        title=title,
        filename="contract.txt",
        file_type="txt",
        status="PROCESSING",
        text_content=text,
        content_hash=f"hash_{title.replace(' ', '_').lower()}",
    )
    session.add(doc)
    session.flush()
    return doc


def test_persist_clauses_records_hierarchy_offsets_and_relationships():
    with SessionLocal() as session:
        user = _create_user(session, "user1@example.com")
        doc = _create_doc(session, user)

        segments = segment_clauses(SAMPLE_HIERARCHICAL_CONTRACT)
        assert len(segments) == 8

        class DummyResult:
            clause_type_by_index = {0: "definitions", 1: "obligations"}
            risk_level_by_index = {0: "LOW", 1: "MEDIUM"}

        clauses = persist_clauses(
            session,
            doc,
            segments,
            pages=[],
            result=DummyResult(),
        )
        session.commit()

        # Reload clauses
        db_clauses = (
            session.scalars(
                select(Clause)
                .where(Clause.document_id == doc.id)
                .order_by(Clause.clause_number)
            )
            .all()
        )

        assert len(db_clauses) == 8
        # Clause order and numbers
        assert [c.clause_number for c in db_clauses] == list(range(1, 9))

        # Labels and levels
        assert [c.label for c in db_clauses] == [
            "1",
            "2",
            "2.1",
            "2.2",
            "(a)",
            "(b)",
            "3",
            "3.1",
        ]
        assert [c.level for c in db_clauses] == [1, 1, 2, 2, 3, 3, 1, 2]

        # Verify parent references
        # Clause 1 (id: db_clauses[0].id) -> None
        assert db_clauses[0].parent_id is None
        # Clause 2 (id: db_clauses[1].id) -> None
        assert db_clauses[1].parent_id is None
        # Clause 2.1 (id: db_clauses[2].id) -> Clause 2
        assert db_clauses[2].parent_id == db_clauses[1].id
        # Clause 2.2 (id: db_clauses[3].id) -> Clause 2
        assert db_clauses[3].parent_id == db_clauses[1].id
        # Clause (a) (id: db_clauses[4].id) -> Clause 2.2
        assert db_clauses[4].parent_id == db_clauses[3].id
        # Clause (b) (id: db_clauses[5].id) -> Clause 2.2
        assert db_clauses[5].parent_id == db_clauses[3].id
        # Clause 3 (id: db_clauses[6].id) -> None
        assert db_clauses[6].parent_id is None
        # Clause 3.1 (id: db_clauses[7].id) -> Clause 3
        assert db_clauses[7].parent_id == db_clauses[6].id

        # Verify ORM relationship: children
        clause2 = db_clauses[1]
        assert {child.id for child in clause2.children} == {
            db_clauses[2].id,
            db_clauses[3].id,
        }

        clause2_2 = db_clauses[3]
        assert {child.id for child in clause2_2.children} == {
            db_clauses[4].id,
            db_clauses[5].id,
        }

        # Verify source text preservation and offsets
        for c in db_clauses:
            assert c.start_offset is not None and c.end_offset is not None
            assert (
                SAMPLE_HIERARCHICAL_CONTRACT[c.start_offset : c.end_offset]
                == c.text
            )


def test_cross_document_parent_protection_raises_error():
    with SessionLocal() as session:
        user = _create_user(session, "crossdoc@example.com")
        doc_a = _create_doc(session, user, title="Document A")
        doc_b = _create_doc(session, user, title="Document B")

        clause_a = Clause(
            document_id=doc_a.id,
            clause_number=1,
            heading="1. Parent in Doc A",
            text="Clause in Document A.",
            label="1",
            level=1,
        )
        session.add(clause_a)
        session.flush()

        clause_b = Clause(
            document_id=doc_b.id,
            clause_number=1,
            heading="1. Child in Doc B",
            text="Clause in Document B.",
            label="1.1",
            level=2,
            parent_id=clause_a.id,  # Points across documents!
        )
        session.add(clause_b)

        with pytest.raises(
            ValueError, match="Parent clause must belong to the same document"
        ):
            session.flush()

        session.rollback()


def test_cross_document_parent_relationship_assignment_raises_error():
    with SessionLocal() as session:
        user = _create_user(session, "crossrel@example.com")
        doc_a = _create_doc(session, user, title="Document A Rel")
        doc_b = _create_doc(session, user, title="Document B Rel")

        clause_a = Clause(
            document_id=doc_a.id,
            clause_number=1,
            heading="1. Clause in Doc A",
            text="Clause in Document A.",
            label="1",
            level=1,
        )
        clause_b = Clause(
            document_id=doc_b.id,
            clause_number=1,
            heading="1. Clause in Doc B",
            text="Clause in Document B.",
            label="1.1",
            level=2,
        )
        session.add_all([clause_a, clause_b])
        session.flush()

        with pytest.raises(
            ValueError, match="Parent clause must belong to the same document"
        ):
            clause_b.parent = clause_a


def test_clause_cannot_be_its_own_parent():
    with SessionLocal() as session:
        user = _create_user(session, "selfparent@example.com")
        doc = _create_doc(session, user, title="Self Parent Doc")

        clause = Clause(
            document_id=doc.id,
            clause_number=1,
            heading="1. Self Parent",
            text="This clause attempts to be its own parent.",
            label="1",
            level=1,
        )
        session.add(clause)
        session.flush()

        with pytest.raises(ValueError, match="A clause cannot be its own parent"):
            clause.parent_id = clause.id
            session.flush()

        session.rollback()


def test_reuse_existing_clause_ids_and_preserve_risk_finding_references():
    with SessionLocal() as session:
        user = _create_user(session, "reuse@example.com")
        doc = _create_doc(session, user, title="Contract for Reuse")

        segments = segment_clauses(SAMPLE_HIERARCHICAL_CONTRACT)

        class MockResult:
            clause_type_by_index = {0: "definitions"}
            risk_level_by_index = {0: "LOW"}

        clauses = persist_clauses(
            session, doc, segments, pages=[], result=MockResult()
        )
        session.flush()

        # Capture original clause IDs
        original_clause_ids = {c.clause_number: c.id for c in clauses}
        assert len(original_clause_ids) == 8

        # Add an analysis and a risk finding pointing to clause 1 and clause 3
        analysis = Analysis(
            document_id=doc.id,
            model_name="rule-based-baseline-v1",
            status="COMPLETED",
            risk_score=25.0,
        )
        session.add(analysis)
        session.flush()

        finding1 = RiskFinding(
            analysis_id=analysis.id,
            clause_id=clauses[0].id,
            rule_code="RULE_DEF",
            severity="LOW",
            title="Definition Review",
            description="Check defined terms.",
        )
        finding2 = RiskFinding(
            analysis_id=analysis.id,
            clause_id=clauses[2].id,
            rule_code="RULE_OBL",
            severity="HIGH",
            title="Obligations Review",
            description="Strict obligations clause.",
        )
        session.add_all([finding1, finding2])
        session.commit()

        doc_id = doc.id
        finding1_id = finding1.id
        finding2_id = finding2.id

    # Re-run persist_clauses on the same document (simulating retry / re-processing)
    with SessionLocal() as session:
        doc = session.get(Document, doc_id)
        segments = segment_clauses(SAMPLE_HIERARCHICAL_CONTRACT)

        reused_clauses = persist_clauses(
            session, doc, segments, pages=[], result=MockResult()
        )
        session.commit()

        # Verify all clause IDs are EXACTLY reused
        new_clause_ids = {c.clause_number: c.id for c in reused_clauses}
        assert new_clause_ids == original_clause_ids

        # Verify finding references remained completely intact
        f1 = session.get(RiskFinding, finding1_id)
        f2 = session.get(RiskFinding, finding2_id)
        assert f1.clause_id == original_clause_ids[1]
        assert f2.clause_id == original_clause_ids[3]
        assert f1.clause.id == original_clause_ids[1]
        assert f2.clause.id == original_clause_ids[3]


def test_legacy_record_support_and_sync():
    with SessionLocal() as session:
        user = _create_user(session, "legacy@example.com")
        doc = _create_doc(
            session,
            user,
            title="Legacy Contract",
            text=SAMPLE_HIERARCHICAL_CONTRACT,
        )

        # Create legacy clauses without label and parent_id
        legacy_clause1 = Clause(
            document_id=doc.id,
            clause_number=1,
            heading="1. Definitions",
            text="In this Agreement the following terms have the meanings given.",
            start_offset=0,
            end_offset=64,
            label=None,
            level=1,
            parent_id=None,
        )
        legacy_clause2 = Clause(
            document_id=doc.id,
            clause_number=2,
            heading="2. Obligations",
            text="2. Obligations\n2.1 The Supplier shall provide the Services with reasonable skill and care.",
            start_offset=66,
            end_offset=165,
            label=None,
            level=1,
            parent_id=None,
        )
        session.add_all([legacy_clause1, legacy_clause2])
        session.commit()

        # 1. Test schema serialization of legacy records
        read1 = ClauseRead.model_validate(legacy_clause1)
        assert read1.id == legacy_clause1.id
        assert read1.label is None
        assert read1.level == 1
        assert read1.parent_id is None

        # 2. Test sync_legacy_clause_hierarchy backfills metadata
        synced = sync_legacy_clause_hierarchy(session, doc)
        session.commit()

        c1 = session.get(Clause, legacy_clause1.id)
        assert c1.label == "1"
        assert c1.level == 1


def test_api_upload_persists_clause_hierarchy_and_exposes_in_detail(client):
    resp = client.post(
        "/api/documents",
        files={
            "file": (
                "contract.txt",
                SAMPLE_HIERARCHICAL_CONTRACT.encode("utf-8"),
                "text/plain",
            )
        },
        data={"title": "Hierarchical Agreement Test"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    clauses = body["clauses"]
    assert len(clauses) == 8

    # Verify labels, levels, and parent_id linkage in API response
    clauses_by_number = {c["clause_number"]: c for c in clauses}
    assert clauses_by_number[1]["label"] == "1"
    assert clauses_by_number[1]["level"] == 1
    assert clauses_by_number[1]["parent_id"] is None

    assert clauses_by_number[2]["label"] == "2"
    assert clauses_by_number[2]["level"] == 1

    clause2_id = clauses_by_number[2]["id"]
    assert clauses_by_number[3]["label"] == "2.1"
    assert clauses_by_number[3]["level"] == 2
    assert clauses_by_number[3]["parent_id"] == clause2_id

    clause2_2_id = clauses_by_number[4]["id"]
    assert clauses_by_number[4]["label"] == "2.2"
    assert clauses_by_number[4]["level"] == 2
    assert clauses_by_number[4]["parent_id"] == clause2_id

    assert clauses_by_number[5]["label"] == "(a)"
    assert clauses_by_number[5]["level"] == 3
    assert clauses_by_number[5]["parent_id"] == clause2_2_id

    # Verify GET detail returns same hierarchy
    detail_resp = client.get(f"/api/documents/{body['id']}")
    assert detail_resp.status_code == 200
    detail_clauses = detail_resp.json()["clauses"]
    assert len(detail_clauses) == 8
    assert detail_clauses[4]["parent_id"] == clause2_2_id


def test_multipage_pdf_clause_hierarchy_and_page_mapping(client):
    data = multi_page_pdf(
        [
            [
                "1. Definitions",
                "Terms used herein have the definitions provided.",
                "2. Obligations",
                "2.1 The Supplier shall perform the duties as required.",
            ],
            [
                "3. Termination",
                "3.1 Either party may terminate on written notice.",
            ],
        ]
    )
    resp = client.post(
        "/api/documents",
        files={"file": ("multipage.pdf", data, "application/pdf")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["page_count"] == 2
    clauses = body["clauses"]
    assert len(clauses) >= 4

    # Pages mapped accurately
    page1_clauses = [c for c in clauses if c["page_number"] == 1]
    page2_clauses = [c for c in clauses if c["page_number"] == 2]
    assert len(page1_clauses) >= 2
    assert len(page2_clauses) >= 1

    # Hierarchy exists across pages
    subclause = next(c for c in clauses if c["label"] == "2.1")
    parent_clause = next(c for c in clauses if c["label"] == "2")
    assert subclause["parent_id"] == parent_clause["id"]
