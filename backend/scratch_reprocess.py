import os
import sys
from uuid import UUID
import json

# Setup path and encoding
sys.path.insert(0, ".")
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.db.session import SessionLocal
from app.models.core import Project, Document, CanonicalLineItem, MatchGroup, Discrepancy, MatchGroupStatus, Severity, DocumentType, ItemCategory
from app.services.crosscheck_service import CrossCheckService


def run():
    db = SessionLocal()
    project_id = UUID("bebfa80a-a6d0-4ace-ab79-0f42d7bdaec9")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        print("Project not found!")
        return

    org_id = project.organization_id
    print(f"Reprocessing project: {project.name} ({project_id}) for org {org_id}...")

    # Fetch extraction line items count
    items = db.query(CanonicalLineItem).filter(
        CanonicalLineItem.project_id == project_id,
        CanonicalLineItem.organization_id == org_id
    ).all()

    d_items = [i for i in items if i.source_type == DocumentType.DESIGN]
    o_items = [i for i in items if i.source_type == DocumentType.ORDER]
    a_items = [i for i in items if i.source_type == DocumentType.ACKNOWLEDGEMENT]

    # Run CrossCheckService
    service = CrossCheckService(db)
    res = service.process_project(project_id, org_id)
    print(f"CrossCheck complete: {res}")

    # Clear and re-query from DB to ensure session freshness
    db.expire_all()

    # Fetch updated MatchGroups and Discrepancies
    match_groups = db.query(MatchGroup).filter(
        MatchGroup.project_id == project_id,
        MatchGroup.organization_id == org_id
    ).all()

    discrepancies = db.query(Discrepancy).filter(
        Discrepancy.project_id == project_id,
        Discrepancy.organization_id == org_id
    ).all()

    # Metrics
    status_counts = {s: 0 for s in MatchGroupStatus}
    for mg in match_groups:
        status_counts[mg.status] += 1

    sev_counts = {s: 0 for s in Severity}
    intro_counts = {"ORDER": 0, "ACKNOWLEDGEMENT": 0, "DESIGN": 0, "NONE": 0}
    for d in discrepancies:
        sev_counts[d.severity] += 1
        if d.introduced_at:
            intro_counts[d.introduced_at.name] = intro_counts.get(d.introduced_at.name, 0) + 1
        else:
            intro_counts["NONE"] += 1

    # Excluded categories count
    excluded_counts = {
        "APPLIANCE": 0,
        "ARCHITECTURAL_ANNOTATION": 0,
        "COMMERCIAL_CHARGE": 0
    }
    for i in items:
        cat_name = getattr(i.item_category, "name", str(i.item_category))
        if cat_name in excluded_counts:
            excluded_counts[cat_name] += 1

    out_lines = []
    out_lines.append("="*50)
    out_lines.append("REQUIRED FINAL METRICS")
    out_lines.append("="*50)
    out_lines.append(f"Design items: {len(d_items)}")
    out_lines.append(f"Order items: {len(o_items)}")
    out_lines.append(f"Ack items: {len(a_items)}")
    out_lines.append(f"Total Match Groups: {len(match_groups)}")
    for status, count in status_counts.items():
        out_lines.append(f"{status.name}: {count}")
    out_lines.append("\nDiscrepancies:")
    for sev, count in sev_counts.items():
        out_lines.append(f"{sev.name}: {count}")
    out_lines.append(f"Total discrepancies: {len(discrepancies)}")
    out_lines.append(f"Introduced ORDER: {intro_counts.get('ORDER', 0)}")
    out_lines.append(f"Introduced ACKNOWLEDGEMENT: {intro_counts.get('ACKNOWLEDGEMENT', 0)}")
    out_lines.append("\nExcluded:")
    for exc, count in excluded_counts.items():
        out_lines.append(f"{exc}: {count}")

    out_lines.append("\n" + "="*50)
    out_lines.append("REQUIRED DETAILED CASES")
    out_lines.append("="*50)

    detailed_cases_skus = [
        "BT36B-2",
        "W3930",
        "WST3057B",
        "WST3657B",
        "24W3618B",
        "24UT3693B-4",
        "BT18-2-L",
        "BT18-2-R",
        "BFHC12",
        "BPFHC12",
        "BPS12",
        "BP52",
        "B18DWB",
        "B18BWD18",
        "SBA36B",
        "SB36B3",
        "21AHSDX7230",
        "GR606F-LP",
        "PWS06DSPSS",
        "FILLER3",
        "FREIGHTSURCHARGE",
        "TARIFFSURCHARGE"
    ]

    for mg in match_groups:
        d_sku = mg.design_item.raw_sku if mg.design_item else "ABSENT"
        o_sku = mg.order_item.raw_sku if mg.order_item else "ABSENT"
        a_sku = mg.ack_item.raw_sku if mg.ack_item else "ABSENT"

        matches_any = any(
            target in d_sku.upper() or target in o_sku.upper() or target in a_sku.upper()
            for target in detailed_cases_skus
        )
        if matches_any:
            mg_discs = [d for d in discrepancies if d.match_group_id == mg.id]
            disc_str = "; ".join([f"{d.field} ({d.severity.name}): {d.explanation}" for d in mg_discs]) if mg_discs else "None"
            intro_str = "; ".join([d.introduced_at.name if d.introduced_at else "N/A" for d in mg_discs]) if mg_discs else "N/A"
            
            d_qty = getattr(mg.design_item, "aggregate_quantity", mg.design_item.quantity) if mg.design_item else None
            o_qty = getattr(mg.order_item, "aggregate_quantity", mg.order_item.quantity) if mg.order_item else None
            a_qty = getattr(mg.ack_item, "aggregate_quantity", mg.ack_item.quantity) if mg.ack_item else None
            
            qty_summary = f"Design={d_qty}, Order={o_qty}, Ack={a_qty}"

            out_lines.append(f"\n--- Match Group ID: {mg.id} ---")
            out_lines.append(f"Design: {d_sku}")
            out_lines.append(f"Order: {o_sku}")
            out_lines.append(f"Ack: {a_sku}")
            out_lines.append(f"Canonical SKU: {mg.final_sku}")
            out_lines.append(f"Aggregate Qty: {qty_summary} (Final={mg.final_quantity})")
            out_lines.append(f"Status: {mg.status.name}")
            out_lines.append(f"Discrepancy: {disc_str}")
            out_lines.append(f"Introduced At: {intro_str}")
            out_lines.append(f"Reason: {mg.final_status or 'RESOLVED'}")

    db.close()

    report_content = "\n".join(out_lines)
    with open("report_f8_2_5.txt", "w", encoding="utf-8") as f:
        f.write(report_content)
    print("Report written to report_f8_2_5.txt successfully!")

if __name__ == "__main__":
    run()

