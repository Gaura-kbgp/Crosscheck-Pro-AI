#!/usr/bin/env python3
"""
F8.2.7 - Comprehensive EXTRA/MISSING/CHANGED/MATCHED audit script.
Produces a full breakdown of every canonical match group.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uuid import UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.core import (
    Project, MatchGroup, MatchGroupStatus, Discrepancy, CanonicalLineItem,
    ItemCategory, DocumentType
)
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

PROJECT_ID = UUID("bebfa80a-a6d0-4ace-ab79-0f42d7bdaec9")

def cat_short(cat):
    if cat is None:
        return "UNKNOWN"
    v = getattr(cat, "value", str(cat))
    return v

def describe_item(item, label):
    if item is None:
        return f"  {label}: ABSENT"
    qty = getattr(item, 'aggregate_quantity', None) or item.quantity
    return (f"  {label}: raw_sku={item.raw_sku!r}, norm_sku={item.normalized_sku!r}, "
            f"qty={qty}, cat={cat_short(item.item_category)}, "
            f"desc={str(item.description or '')[:60]!r}, "
            f"dims={item.dimensions}")

def run_audit():
    session = Session()
    try:
        project = session.query(Project).filter_by(id=PROJECT_ID).first()
        if not project:
            print(f"Project {PROJECT_ID} not found")
            return

        mgs = (session.query(MatchGroup)
               .filter_by(project_id=PROJECT_ID)
               .options(
                   __import__('sqlalchemy.orm', fromlist=['joinedload']).joinedload(MatchGroup.discrepancies),
                   __import__('sqlalchemy.orm', fromlist=['joinedload']).joinedload(MatchGroup.design_item),
                   __import__('sqlalchemy.orm', fromlist=['joinedload']).joinedload(MatchGroup.order_item),
                   __import__('sqlalchemy.orm', fromlist=['joinedload']).joinedload(MatchGroup.ack_item),
               )
               .all())

        from collections import defaultdict
        by_status = defaultdict(list)
        for mg in mgs:
            by_status[mg.status].append(mg)

        # Count discrepancies by severity
        all_discs = session.query(Discrepancy).filter_by(project_id=PROJECT_ID).all()
        from collections import Counter
        disc_by_sev = Counter(getattr(d.severity, 'value', str(d.severity)) for d in all_discs)

        print("=" * 70)
        print("F8.2.7 COMPREHENSIVE AUDIT REPORT")
        print(f"Project: {project.name} ({PROJECT_ID})")
        print("=" * 70)
        print()
        print("--- SUMMARY ---")
        for status in [MatchGroupStatus.MATCHED, MatchGroupStatus.CHANGED,
                       MatchGroupStatus.MISSING, MatchGroupStatus.EXTRA,
                       MatchGroupStatus.UNCERTAIN]:
            print(f"  {status.value}: {len(by_status.get(status, []))}")
        print(f"  Total MGs: {len(mgs)}")
        print()
        print("--- DISCREPANCIES ---")
        for sev, cnt in sorted(disc_by_sev.items()):
            print(f"  {sev}: {cnt}")
        print(f"  Total: {len(all_discs)}")
        print()

        # Category breakdown
        from collections import Counter
        all_cats = Counter()
        for mg in mgs:
            for item in [mg.design_item, mg.order_item, mg.ack_item]:
                if item:
                    all_cats[cat_short(item.item_category)] += 1
        print("--- ITEM CATEGORIES ---")
        for cat, cnt in sorted(all_cats.items()):
            print(f"  {cat}: {cnt}")
        print()

        # ================================================================
        # EXTRA DETAILED BREAKDOWN
        # ================================================================
        extras = by_status.get(MatchGroupStatus.EXTRA, [])
        print("=" * 70)
        print(f"EXTRA CANONICAL GROUPS ({len(extras)} total)")
        print("=" * 70)
        for i, mg in enumerate(extras, 1):
            di, oi, ai = mg.design_item, mg.order_item, mg.ack_item
            # Determine primary item for this EXTRA group
            primary = oi or ai or di
            canonical_sku = primary.normalized_sku if primary else "?"
            raw_sku = primary.raw_sku if primary else "?"
            cat = cat_short(primary.item_category) if primary else "UNKNOWN"
            d_qty = getattr(di, 'aggregate_quantity', None) or (di.quantity if di else None)
            o_qty = getattr(oi, 'aggregate_quantity', None) or (oi.quantity if oi else None)
            a_qty = getattr(ai, 'aggregate_quantity', None) or (ai.quantity if ai else None)
            desc = (primary.description or "")[:80] if primary else ""
            dims = primary.dimensions if primary else None

            # Source context
            source = []
            if di: source.append("D")
            if oi: source.append("O")
            if ai: source.append("A")

            # Discrepancies for this MG
            mg_discs = [d for d in all_discs if d.match_group_id == mg.id]
            disc_summary = []
            for d in mg_discs:
                sev = getattr(d.severity, 'value', str(d.severity))
                explanation_clean = (d.explanation[:80] or "").encode('ascii', errors='replace').decode('ascii')
                disc_summary.append(f"{d.field}({sev}): {explanation_clean}")

            print(f"\n  [{i}] Canonical: {canonical_sku}")
            print(f"      Raw SKU: {raw_sku}")
            print(f"      Category: {cat}")
            print(f"      D/O/A: {d_qty or 'ABSENT'}/{o_qty or 'ABSENT'}/{a_qty or 'ABSENT'}")
            print(f"      Sources: {'/'.join(source) or 'NONE'}")
            print(f"      Description: {desc!r}")
            print(f"      Dimensions: {dims}")
            if disc_summary:
                for ds in disc_summary:
                    print(f"      Discrepancy: {ds}")
            else:
                print(f"      Discrepancy: None (excluded or status only)")

        # ================================================================
        # MISSING DETAILED BREAKDOWN
        # ================================================================
        missings = by_status.get(MatchGroupStatus.MISSING, [])
        print()
        print("=" * 70)
        print(f"MISSING CANONICAL GROUPS ({len(missings)} total)")
        print("=" * 70)
        for i, mg in enumerate(missings, 1):
            di, oi, ai = mg.design_item, mg.order_item, mg.ack_item
            primary = di or oi or ai
            canonical_sku = primary.normalized_sku if primary else "?"
            raw_sku = primary.raw_sku if primary else "?"
            cat = cat_short(primary.item_category) if primary else "UNKNOWN"
            d_qty = getattr(di, 'aggregate_quantity', None) or (di.quantity if di else None)
            o_qty = getattr(oi, 'aggregate_quantity', None) or (oi.quantity if oi else None)
            a_qty = getattr(ai, 'aggregate_quantity', None) or (ai.quantity if ai else None)
            desc = (primary.description or "")[:80] if primary else ""
            dims = primary.dimensions if primary else None

            mg_discs = [d for d in all_discs if d.match_group_id == mg.id]
            disc_summary = []
            for d in mg_discs:
                sev = getattr(d.severity, 'value', str(d.severity))
                explanation_clean = (d.explanation[:100] or "").encode('ascii', errors='replace').decode('ascii')
                disc_summary.append(f"{d.field}({sev}): {explanation_clean}")

            print(f"\n  [{i}] Canonical: {canonical_sku}")
            print(f"      Raw SKU: {raw_sku}")
            print(f"      Category: {cat}")
            print(f"      D/O/A: {d_qty or 'ABSENT'}/{o_qty or 'ABSENT'}/{a_qty or 'ABSENT'}")
            print(f"      Description: {desc!r}")
            print(f"      Dimensions: {dims}")
            if disc_summary:
                for ds in disc_summary:
                    print(f"      Discrepancy: {ds}")

        # ================================================================
        # CHANGED DETAILED BREAKDOWN
        # ================================================================
        changed = by_status.get(MatchGroupStatus.CHANGED, [])
        print()
        print("=" * 70)
        print(f"CHANGED CANONICAL GROUPS ({len(changed)} total)")
        print("=" * 70)
        for i, mg in enumerate(changed, 1):
            di, oi, ai = mg.design_item, mg.order_item, mg.ack_item
            primary = di or oi or ai
            canonical_sku = primary.normalized_sku if primary else "?"
            cat = cat_short(primary.item_category) if primary else "UNKNOWN"
            d_qty = getattr(di, 'aggregate_quantity', None) or (di.quantity if di else None)
            o_qty = getattr(oi, 'aggregate_quantity', None) or (oi.quantity if oi else None)
            a_qty = getattr(ai, 'aggregate_quantity', None) or (ai.quantity if ai else None)

            mg_discs = [d for d in all_discs if d.match_group_id == mg.id]
            print(f"\n  [{i}] {canonical_sku} | cat={cat} | D/O/A={d_qty or 'ABSENT'}/{o_qty or 'ABSENT'}/{a_qty or 'ABSENT'}")
            for d in mg_discs:
                sev = getattr(d.severity, 'value', str(d.severity))
                intro = getattr(d.introduced_at, 'value', str(d.introduced_at)) if d.introduced_at else 'N/A'
                print(f"      {d.field}({sev}) intro={intro}: {d.explanation[:100]}")

        # ================================================================
        # MATCHED SANITY CHECK
        # ================================================================
        matched = by_status.get(MatchGroupStatus.MATCHED, [])
        print()
        print("=" * 70)
        print(f"MATCHED SANITY CHECK ({len(matched)} total)")
        print("=" * 70)
        for mg in matched:
            di, oi, ai = mg.design_item, mg.order_item, mg.ack_item
            primary = di or oi or ai
            if not primary:
                continue
            canonical_sku = primary.normalized_sku
            cat = cat_short(primary.item_category)
            d_qty = getattr(di, 'aggregate_quantity', None) or (di.quantity if di else None)
            o_qty = getattr(oi, 'aggregate_quantity', None) or (oi.quantity if oi else None)
            a_qty = getattr(ai, 'aggregate_quantity', None) or (ai.quantity if ai else None)
            mg_discs = [d for d in all_discs if d.match_group_id == mg.id]
            flag = " *** HAS DISCREPANCIES ***" if mg_discs else ""
            d_sku = di.raw_sku if di else "-"
            o_sku = oi.raw_sku if oi else "-"
            a_sku = ai.raw_sku if ai else "-"
            print(f"  {canonical_sku} | {cat} | D={d_sku}({d_qty}) O={o_sku}({o_qty}) A={a_sku}({a_qty}){flag}")

        print()
        print("=" * 70)
        print("AUDIT COMPLETE")
        print("=" * 70)

    finally:
        session.close()

if __name__ == "__main__":
    run_audit()
