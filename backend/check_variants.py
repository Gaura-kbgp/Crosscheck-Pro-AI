import os
import sys
from uuid import UUID

sys.path.insert(0, ".")

from app.db.session import SessionLocal
from app.models.core import CanonicalLineItem, DocumentType
from app.engines.normalization import check_canonical_equivalence

db = SessionLocal()
project_id = UUID("bebfa80a-a6d0-4ace-ab79-0f42d7bdaec9")

skus_to_check = ["BFHC12", "BPFHC12", "BPS12", "BP52", "B18DWB", "B18BWD18", "SBA36B", "SB36B3"]

items = db.query(CanonicalLineItem).filter(
    CanonicalLineItem.project_id == project_id
).all()

for target in skus_to_check:
    matched_items = [i for i in items if i.raw_sku and target in i.raw_sku.upper()]
    for mi in matched_items:
        print(f"[{mi.source_type.name}] SKU='{mi.raw_sku}', Norm='{mi.normalized_sku}', Desc='{mi.description}', Dims={mi.dimensions}, Cat={mi.item_category.name}, Finish='{mi.finish}', Door='{mi.door_style}'")

# Let's test equivalence between design BFHC12 and order BFHC12
d_bfhc = next((i for i in items if i.source_type == DocumentType.DESIGN and i.raw_sku == "BFHC12"), None)
o_bfhc = next((i for i in items if i.source_type == DocumentType.ORDER and i.raw_sku == "BFHC12"), None)
a_bpfhc = next((i for i in items if i.source_type == DocumentType.ACKNOWLEDGEMENT and "BPFHC" in (i.raw_sku or "")), None)

if d_bfhc and o_bfhc:
    print("\nChecking D vs O for BFHC12:")
    print(check_canonical_equivalence(
        sku1=d_bfhc.raw_sku, desc1=d_bfhc.description, dims1=d_bfhc.dimensions, cat1=d_bfhc.item_category,
        sku2=o_bfhc.raw_sku, desc2=o_bfhc.description, dims2=o_bfhc.dimensions, cat2=o_bfhc.item_category
    ))

if o_bfhc and a_bpfhc:
    print("\nChecking O vs A for BFHC12 / BPFHC12:")
    print(check_canonical_equivalence(
        sku1=o_bfhc.raw_sku, desc1=o_bfhc.description, dims1=o_bfhc.dimensions, cat1=o_bfhc.item_category,
        sku2=a_bpfhc.raw_sku, desc2=a_bpfhc.description, dims2=a_bpfhc.dimensions, cat2=a_bpfhc.item_category
    ))

db.close()
