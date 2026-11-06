import uuid
from sqlalchemy.orm import Session
from app.models.core import (
    Project, ProjectStatus, Document, DocumentType, DocumentStatus,
    CanonicalLineItem, ItemCategory, MatchGroup, MatchGroupStatus,
    Discrepancy, Severity,
)

# Real, verified data from the Chesapeake Bay Marsh Display R3 job (the same
# job used to live-test P1-1/P1-2 extraction accuracy against the external
# testing review's hand-built answer key) — not fabricated sample data.
_SAMPLE_PAIRS = [
    {
        "sku": "MCV96",
        "description": "Crown top moulding",
        "field": "quantity",
        "design_value": "1",
        "order_value": "2",
        "ack_value": "2",
        "introduced_at": DocumentType.ORDER,
        "severity": Severity.WARNING,
        "explanation": "Quantity changed from 1 (Design) to 2 (Purchase Order) for crown top moulding MCV96 — confirmed by the manufacturer at the new quantity.",
    },
    {
        "sku": "WCC3042R",
        "description": "Wall corner cabinet",
        "field": "construction",
        "design_value": "Furniture Board",
        "order_value": "Furniture Board",
        "ack_value": "PLY (plywood upgrade, costs more)",
        "introduced_at": DocumentType.ACKNOWLEDGEMENT,
        "severity": Severity.WARNING,
        "explanation": "Manufacturer confirmed a plywood construction upgrade not present in the original Design or Purchase Order — dealer should confirm the added cost with the customer.",
    },
]

_MATCHED_ITEM = {"sku": "TUKT", "description": "Touch-up kit"}


def create_sample_project(db: Session, organization_id) -> None:
    """
    P2-1: every new organization gets one pre-checked sample project so the
    first screen after signup is never empty. Built directly from database
    rows (no AI extraction call) using real, previously-verified Chesapeake
    Bay discrepancy data, so it's instant and free to create at signup time.
    """
    project = Project(
        id=uuid.uuid4(),
        organization_id=organization_id,
        name="Chesapeake Bay Display (Sample)",
        customer_name="Chesapeake Bay Cabinets",
        dealer_name="Sample Dealer",
        status=ProjectStatus.COMPLETED,
        is_sample=True,
    )
    db.add(project)
    db.flush()

    docs = {}
    for doc_type in (DocumentType.DESIGN, DocumentType.ORDER, DocumentType.ACKNOWLEDGEMENT):
        doc = Document(
            id=uuid.uuid4(),
            project_id=project.id,
            organization_id=organization_id,
            document_type=doc_type,
            original_filename=f"sample_{doc_type.value.lower()}.pdf",
            storage_path=f"sample/{project.id}/{doc_type.value.lower()}.pdf",
            mime_type="application/pdf",
            file_size=0,
            status=DocumentStatus.COMPLETED,
        )
        db.add(doc)
        docs[doc_type] = doc
    db.flush()

    def _line_item(doc_type: DocumentType, sku: str, description: str, quantity):
        item = CanonicalLineItem(
            id=uuid.uuid4(),
            project_id=project.id,
            organization_id=organization_id,
            document_id=docs[doc_type].id,
            source_type=doc_type,
            raw_sku=sku,
            normalized_sku=sku,
            description=description,
            item_category=ItemCategory.MOLDING,
            quantity=quantity,
        )
        db.add(item)
        return item

    for pair in _SAMPLE_PAIRS:
        design_item = _line_item(DocumentType.DESIGN, pair["sku"], pair["description"], 1)
        order_item = _line_item(DocumentType.ORDER, pair["sku"], pair["description"], 1)
        ack_item = _line_item(DocumentType.ACKNOWLEDGEMENT, pair["sku"], pair["description"], 1)
        db.flush()

        match_group = MatchGroup(
            id=uuid.uuid4(),
            project_id=project.id,
            organization_id=organization_id,
            design_item_id=design_item.id,
            cabinet_list_item_id=order_item.id,
            ack_item_id=ack_item.id,
            status=MatchGroupStatus.CHANGED,
            final_sku=pair["sku"],
        )
        db.add(match_group)
        db.flush()

        db.add(Discrepancy(
            id=uuid.uuid4(),
            project_id=project.id,
            organization_id=organization_id,
            match_group_id=match_group.id,
            field=pair["field"],
            source_values={
                "design": pair["design_value"],
                "order": pair["order_value"],
                "acknowledgement": pair["ack_value"],
            },
            comparison_values={"expected": pair["design_value"], "actual": pair["ack_value"]},
            introduced_at=pair["introduced_at"],
            status="OPEN",
            severity=pair["severity"],
            explanation=pair["explanation"],
        ))

    # One clean matched item too, so the sample isn't all red flags.
    matched_design = _line_item(DocumentType.DESIGN, _MATCHED_ITEM["sku"], _MATCHED_ITEM["description"], 1)
    matched_order = _line_item(DocumentType.ORDER, _MATCHED_ITEM["sku"], _MATCHED_ITEM["description"], 1)
    matched_ack = _line_item(DocumentType.ACKNOWLEDGEMENT, _MATCHED_ITEM["sku"], _MATCHED_ITEM["description"], 1)
    db.flush()
    db.add(MatchGroup(
        id=uuid.uuid4(),
        project_id=project.id,
        organization_id=organization_id,
        design_item_id=matched_design.id,
        cabinet_list_item_id=matched_order.id,
        ack_item_id=matched_ack.id,
        status=MatchGroupStatus.MATCHED,
        final_sku=_MATCHED_ITEM["sku"],
    ))

    db.commit()
