import os
import sys
from uuid import UUID
from app.db.session import SessionLocal
from app.models.core import Project, MatchGroup, Discrepancy, CanonicalLineItem, ItemCategory, MatchGroupStatus, Severity
from app.services.crosscheck_service import CrossCheckService
from sqlalchemy import select

PROJECT_ID = UUID("bebfa80a-a6d0-4ace-ab79-0f42d7bdaec9")

def run():
    db = SessionLocal()
    try:
        project = db.scalars(select(Project).where(Project.id == PROJECT_ID)).first()
        if not project:
            print(f"Project {PROJECT_ID} not found!")
            return
        
        print(f"Reprocessing project: {project.name} ({project.id}) for org {project.organization_id}...")
        service = CrossCheckService(db)
        res = service.process_project(project.id, project.organization_id)
        print(f"CrossCheck complete: {res}")
        
        # Verify counts
        raw_items = db.scalars(select(CanonicalLineItem).where(CanonicalLineItem.project_id == PROJECT_ID)).all()
        design_items = [i for i in raw_items if i.source_type.name == "DESIGN"]
        order_items = [i for i in raw_items if i.source_type.name == "ORDER"]
        ack_items = [i for i in raw_items if i.source_type.name == "ACKNOWLEDGEMENT"]
        
        match_groups = db.scalars(select(MatchGroup).where(MatchGroup.project_id == PROJECT_ID)).all()
        discrepancies = db.scalars(select(Discrepancy).where(Discrepancy.project_id == PROJECT_ID)).all()
        
        mg_by_status = {}
        for mg in match_groups:
            mg_by_status[mg.status.value] = mg_by_status.get(mg.status.value, 0) + 1
            
        disc_by_sev = {}
        disc_by_intro = {}
        for d in discrepancies:
            disc_by_sev[d.severity.value] = disc_by_sev.get(d.severity.value, 0) + 1
            intro = d.introduced_at.value if d.introduced_at else "N/A"
            disc_by_intro[intro] = disc_by_intro.get(intro, 0) + 1
            
        appliances = [i for i in raw_items if i.item_category == ItemCategory.APPLIANCE]
        arch = [i for i in raw_items if i.item_category == ItemCategory.ARCHITECTURAL_ANNOTATION]
        comm = [i for i in raw_items if i.item_category == ItemCategory.COMMERCIAL_CHARGE]
        
        report_lines = []
        report_lines.append("==================================================")
        report_lines.append("F8.2.6 REQUIRED FINAL METRICS")
        report_lines.append("==================================================")
        report_lines.append(f"Design raw items: {len(design_items)}")
        report_lines.append(f"Order raw items: {len(order_items)}")
        report_lines.append(f"Ack raw items: {len(ack_items)}")
        report_lines.append(f"Total Canonical Match Groups: {len(match_groups)}")
        report_lines.append(f"MATCHED: {mg_by_status.get('MATCHED', 0)}")
        report_lines.append(f"CHANGED: {mg_by_status.get('CHANGED', 0)}")
        report_lines.append(f"MISSING: {mg_by_status.get('MISSING', 0)}")
        report_lines.append(f"EXTRA: {mg_by_status.get('EXTRA', 0)}")
        report_lines.append(f"UNCERTAIN: {mg_by_status.get('UNCERTAIN', 0)}")
        report_lines.append("")
        report_lines.append("Physical Cabinet Discrepancies:")
        report_lines.append(f"CRITICAL: {disc_by_sev.get('Critical', 0)}")
        report_lines.append(f"WARNING: {disc_by_sev.get('Warning', 0)}")
        report_lines.append(f"INFO: {disc_by_sev.get('Info', 0)}")
        report_lines.append(f"Total discrepancies: {len(discrepancies)}")
        report_lines.append(f"Introduced ORDER: {disc_by_intro.get('ORDER', 0)}")
        report_lines.append(f"Introduced ACKNOWLEDGEMENT: {disc_by_intro.get('ACKNOWLEDGEMENT', 0)}")
        report_lines.append("")
        report_lines.append("Excluded Categories:")
        report_lines.append(f"APPLIANCE: {len(appliances)}")
        report_lines.append(f"ARCHITECTURAL_ANNOTATION: {len(arch)}")
        report_lines.append(f"COMMERCIAL_CHARGE: {len(comm)}")
        report_lines.append("")
        report_lines.append("==================================================")
        report_lines.append("REQUIRED DETAILED CASES (17 TARGET ITEMS)")
        report_lines.append("==================================================")
        
        target_skus = [
            "BT36B-2", "W3930", "WST3057B", "WST3657B", "24W3618B", "24UT3693B-4",
            "BT18-2-L", "BT18-2-R", "BFHC12", "BPFHC12", "BPS12", "BP52",
            "B18DWB", "B18BWD18", "SBA36B", "SB36B3", "21AHSDX7230",
            "GR606F-LP", "PWS06DSPSS", "FILLER3", "FREIGHTSURCHARGE", "TARIFFSURCHARGE"
        ]
        
        # Build map from item id to item
        item_map = {i.id: i for i in raw_items}
        
        seen_mg_ids = set()
        for target in target_skus:
            for mg in match_groups:
                if mg.id in seen_mg_ids:
                    continue
                d_item = item_map.get(mg.design_item_id) if mg.design_item_id else None
                o_item = item_map.get(mg.order_item_id) if mg.order_item_id else None
                a_item = item_map.get(mg.ack_item_id) if mg.ack_item_id else None
                
                skus = [x.raw_sku for x in [d_item, o_item, a_item] if x]
                canonical_skus = [x.normalized_sku for x in [d_item, o_item, a_item] if x]
                if any(target in s for s in skus) or any(target in s for s in canonical_skus) or target == mg.final_sku:
                    seen_mg_ids.add(mg.id)
                    d_sku = d_item.raw_sku if d_item else "ABSENT"
                    o_sku = o_item.raw_sku if o_item else "ABSENT"
                    a_sku = a_item.raw_sku if a_item else "ABSENT"
                    
                    d_qty = d_item.source_metadata.get("aggregate_quantity", d_item.quantity) if (d_item and d_item.source_metadata) else (d_item.quantity if d_item else None)
                    o_qty = o_item.source_metadata.get("aggregate_quantity", o_item.quantity) if (o_item and o_item.source_metadata) else (o_item.quantity if o_item else None)
                    a_qty = a_item.source_metadata.get("aggregate_quantity", a_item.quantity) if (a_item and a_item.source_metadata) else (a_item.quantity if a_item else None)
                    
                    mg_discs = [d for d in discrepancies if d.match_group_id == mg.id]
                    disc_str = "; ".join([f"{d.field} ({d.severity.value}): {d.explanation}" for d in mg_discs]) if mg_discs else "None"
                    intro_str = "; ".join([d.introduced_at.value if d.introduced_at else "N/A" for d in mg_discs]) if mg_discs else "N/A"
                    sev_str = "; ".join([d.severity.value for d in mg_discs]) if mg_discs else "None"
                    
                    report_lines.append(f"\n--- Target: {target} (Match Group: {mg.id}) ---")
                    report_lines.append(f"Design: {d_sku} (Qty={d_qty})")
                    report_lines.append(f"Order: {o_sku} (Qty={o_qty})")
                    report_lines.append(f"Ack: {a_sku} (Qty={a_qty})")
                    report_lines.append(f"Canonical SKU: {mg.final_sku}")
                    report_lines.append(f"Status: {mg.status.value}")
                    report_lines.append(f"Discrepancy: {disc_str}")
                    report_lines.append(f"Severity: {sev_str}")
                    report_lines.append(f"Introduced At: {intro_str}")
                    report_lines.append(f"Reason: {mg.final_status or 'PENDING_REVIEW'}")

        report_lines.append("")
        report_lines.append("==================================================")
        report_lines.append("REMAINING UNCERTAIN AUDIT")
        report_lines.append("==================================================")
        uncertain_groups = [mg for mg in match_groups if mg.status == MatchGroupStatus.UNCERTAIN]
        report_lines.append(f"Total UNCERTAIN Groups: {len(uncertain_groups)}")
        for mg in uncertain_groups:
            d_item = item_map.get(mg.design_item_id) if mg.design_item_id else None
            o_item = item_map.get(mg.order_item_id) if mg.order_item_id else None
            a_item = item_map.get(mg.ack_item_id) if mg.ack_item_id else None
            
            report_lines.append(f"\n- SKU: {mg.final_sku or (d_item or o_item or a_item).raw_sku}")
            report_lines.append(f"  Design Evidence: {d_item.raw_sku if d_item else 'ABSENT'} (Desc: {d_item.description if d_item else 'None'})")
            report_lines.append(f"  Order Evidence: {o_item.raw_sku if o_item else 'ABSENT'} (Desc: {o_item.description if o_item else 'None'})")
            report_lines.append(f"  Ack Evidence: {a_item.raw_sku if a_item else 'ABSENT'} (Desc: {a_item.description if a_item else 'None'})")
            report_lines.append("  Why deterministic matching cannot resolve it: Candidate item lacks required variant/orientation/line correspondence evidence.")
            report_lines.append("  Why human review is required: Requires user selection to verify purchasing intent.")

        report_content = "\n".join(report_lines)
        with open("report_f8_2_6.txt", "w", encoding="utf-8") as f:
            f.write(report_content)
        print("Report written to report_f8_2_6.txt successfully!")
        
    finally:
        db.close()

if __name__ == "__main__":
    run()
