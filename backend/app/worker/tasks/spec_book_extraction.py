"""
Background extraction for Settings → Manufacturer → Upload Specification
Book (PDF, CSV, or Excel) → Extract codes. Mirrors the existing Design/
Order/Ack pipeline's Celery shared_task + *_sync fallback pattern in
app/worker/tasks/processing.py.

A PDF goes through AI extraction (OpenAIProvider.extract_spec_book_codes).
A CSV/Excel file is ALREADY structured data — it is parsed deterministically
(no AI call, no guessing) by matching common column-header spellings for
code/description/category. Either path produces the exact same staging
rows and goes through the exact same human Review → Approve step; nothing
is ever written to ManufacturerCodeDictionary directly.
"""
import csv
import io
import re
import uuid
from typing import Any, Dict, List, Optional

from celery import shared_task

try:
    import openpyxl
except ImportError:
    openpyxl = None

from app.db.session import SessionLocal
from app.models.core import ManufacturerSpecBook, ManufacturerSpecBookRow, SpecBookStatus, ItemCategory
from app.engines.normalization import normalize_sku
from app.integrations.ai import get_ai_provider


def _get_db():
    return SessionLocal()


# Deterministic column-header matching for CSV/Excel spec books — real
# manufacturer exports rarely use our own exact schema column names, so we
# match common real-world variants. This is a lookup match, never a guess
# about the DATA itself: if no code-like column is found at all, extraction
# fails loudly rather than silently returning nothing.
_CODE_HEADER_ALIASES = {"code", "sku", "item", "itemcode", "itemnumber", "item#", "productcode", "model", "modelnumber", "partnumber", "part#", "cabinetcode"}
_DESC_HEADER_ALIASES = {"description", "desc", "name", "productname", "productdescription", "itemdescription", "itemname"}
_CATEGORY_HEADER_ALIASES = {"category", "type", "producttype", "itemtype", "producttcategory"}

# Category keyword inference is a CANDIDATE only — every row still goes
# through mandatory human review before approval, exactly like an AI guess
# would. A value that matches none of these stays UNKNOWN, never guessed.
_CATEGORY_KEYWORDS = [
    (ItemCategory.COMMERCIAL_CHARGE, ["charge", "freight", "surcharge", "tariff", "shipping"]),
    (ItemCategory.MOLDING, ["molding", "moulding", "crown", "trim"]),
    (ItemCategory.APPLIANCE, ["appliance", "range", "refrigerator", "dishwasher", "microwave"]),
    (ItemCategory.ARCHITECTURAL_ANNOTATION, ["architectural", "annotation", "soffit"]),
    (ItemCategory.ACCESSORY, ["accessory", "hardware", "hinge", "pull", "knob"]),
    (ItemCategory.PANEL, ["panel"]),
    (ItemCategory.FILLER, ["filler"]),
    (ItemCategory.CABINET, ["cabinet", "base", "wall", "vanity", "tall"]),
]


def _normalize_header(h: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(h or "").strip().lower())


def _infer_category(raw: Optional[str]) -> ItemCategory:
    if not raw:
        return ItemCategory.UNKNOWN
    try:
        return ItemCategory(raw.strip().upper())
    except ValueError:
        pass
    lowered = raw.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(k in lowered for k in keywords):
            return category
    return ItemCategory.UNKNOWN


def parse_tabular_spec_book(filename: str, content: bytes) -> List[Dict[str, Any]]:
    """
    Deterministically parses a CSV/Excel spec book — no AI call. Every
    extracted row's code/description are exactly what was in the cell, never
    normalized or corrected here (normalization happens later, non-
    destructively, in _run_extraction). category is a best-effort keyword
    candidate; a reviewer can always correct it before approval.
    """
    lower = filename.lower()
    if lower.endswith(".csv"):
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        rows_iter = iter(reader)
        try:
            headers = next(rows_iter)
        except StopIteration:
            return []
        raw_rows = list(rows_iter)
    elif lower.endswith(".xlsx"):
        if not openpyxl:
            raise ValueError("Excel parsing is unavailable on this server")
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        headers = list(next(rows_iter, []))
        raw_rows = [list(r) for r in rows_iter if r and any(v is not None for v in r)]
    else:
        raise ValueError(f"Unsupported tabular format: {filename}")

    normalized_headers = [_normalize_header(h) for h in headers]
    code_col = next((i for i, h in enumerate(normalized_headers) if h in _CODE_HEADER_ALIASES), None)
    if code_col is None:
        raise ValueError(
            "Could not find a code/SKU column in this file. Expected a header like "
            "'Code', 'SKU', 'Item #', or 'Model Number'."
        )
    desc_col = next((i for i, h in enumerate(normalized_headers) if h in _DESC_HEADER_ALIASES), None)
    category_col = next((i for i, h in enumerate(normalized_headers) if h in _CATEGORY_HEADER_ALIASES), None)

    items: List[Dict[str, Any]] = []
    for row in raw_rows:
        if code_col >= len(row):
            continue
        code = row[code_col]
        if code is None or not str(code).strip():
            continue  # never fabricate a code for a blank cell
        description = str(row[desc_col]).strip() if desc_col is not None and desc_col < len(row) and row[desc_col] is not None else None
        category_raw = str(row[category_col]).strip() if category_col is not None and category_col < len(row) and row[category_col] is not None else None
        items.append({
            "code": str(code).strip(),
            "description": description,
            "category": _infer_category(category_raw).value,
            "confidence": 1.0,  # deterministic: exactly what was in the cell, not a probabilistic guess
            "page_number": None,
            "source_text": None,
        })
    return items


def _run_extraction(spec_book_id_str: str):
    spec_book_id = uuid.UUID(spec_book_id_str)

    db = _get_db()
    try:
        book = db.query(ManufacturerSpecBook).filter(ManufacturerSpecBook.id == spec_book_id).first()
        if not book:
            return
        book.status = SpecBookStatus.EXTRACTING
        book.error = None
        storage_path = book.storage_path
        db.commit()
    finally:
        db.close()

    try:
        from app.integrations.storage import StorageService
        file_bytes = StorageService().get_file(storage_path)

        filename = book.original_filename
        if filename.lower().endswith((".csv", ".xlsx")):
            raw_items = parse_tabular_spec_book(filename, file_bytes)
        else:
            ai = get_ai_provider()
            raw_items = ai.extract_spec_book_codes(file_bytes)

        db = _get_db()
        try:
            # A retried/duplicate task run must never create duplicate
            # candidate rows for the same book (§ Celery retry safety,
            # matching the existing pipeline's guarantee) — clear any rows
            # from a prior attempt on this book before writing fresh ones.
            db.query(ManufacturerSpecBookRow).filter(ManufacturerSpecBookRow.spec_book_id == spec_book_id).delete()

            for item in raw_items:
                raw_code = (item.get("code") or "").strip()
                if not raw_code:
                    continue  # never fabricate a code where none was printed
                normalized = normalize_sku(raw_code)
                if not normalized:
                    continue

                category_raw = (item.get("category") or "UNKNOWN").strip().upper()
                try:
                    category = ItemCategory(category_raw)
                except ValueError:
                    category = ItemCategory.UNKNOWN

                confidence = item.get("confidence")
                try:
                    confidence = float(confidence) if confidence is not None else None
                except (TypeError, ValueError):
                    confidence = None

                db.add(ManufacturerSpecBookRow(
                    id=uuid.uuid4(), spec_book_id=spec_book_id, manufacturer_id=book.manufacturer_id,
                    raw_code=raw_code, normalized_code=normalized,
                    description=item.get("description"), category=category, confidence=confidence,
                    page_number=item.get("page_number"), source_text=item.get("source_text"),
                ))

            book = db.query(ManufacturerSpecBook).filter(ManufacturerSpecBook.id == spec_book_id).first()
            book.status = SpecBookStatus.EXTRACTED
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        db = _get_db()
        try:
            book = db.query(ManufacturerSpecBook).filter(ManufacturerSpecBook.id == spec_book_id).first()
            if book:
                book.status = SpecBookStatus.FAILED
                book.error = {"message": str(exc)}
                db.commit()
        finally:
            db.close()
        raise


@shared_task(bind=True, max_retries=2)
def extract_spec_book_task(self, spec_book_id_str: str):
    try:
        _run_extraction(spec_book_id_str)
    except Exception as exc:
        try:
            self.retry(exc=exc, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            pass  # _run_extraction already marked the book FAILED with the error detail


def extract_spec_book_task_sync(spec_book_id_str: str):
    try:
        _run_extraction(spec_book_id_str)
    except Exception:
        pass  # already recorded on the book by _run_extraction
