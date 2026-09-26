"""
Manufacturer & Cabinet Code Dictionary management service.

Tenant isolation rule (non-negotiable): a manufacturer is visible to an
organization only if it is global (organization_id IS NULL, is_global=True —
system/seed data, e.g. the Phase A "Yorktowne" seed) or owned by that exact
organization_id. A manufacturer belonging to another organization must be
completely invisible — not just read-only — so ID-guessing an existing
resource ID from another tenant returns 404, never 403 (which would leak
existence). Global manufacturers ARE read-only to every tenant: this API
never lets a tenant create or edit a global entry, only their own private
ones (`ManufacturerCreate` doesn't even accept `is_global`).
"""
import csv
import io
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings

try:
    import openpyxl
except ImportError:
    openpyxl = None

from app.core.exceptions import ResourceNotFoundError, BusinessLogicError
from app.models.core import ItemCategory, Manufacturer, ManufacturerCodeDictionary
from app.engines.normalization import normalize_sku
from app.schemas.manufacturer import (
    ManufacturerCreate, ManufacturerUpdate, ManufacturerResponse,
    ManufacturerCodeCreate, ManufacturerCodeUpdate, ManufacturerCodeResponse,
    BulkImportPreview, BulkImportResult, BulkImportRowError,
)

_IMPORT_COLUMNS = ["code", "description", "category", "alias_group", "is_current", "source_version", "effective_from", "effective_to"]
_TRUE_STRINGS = {"1", "true", "yes", "y"}
_FALSE_STRINGS = {"0", "false", "no", "n"}


class ManufacturerService:
    def __init__(self, db: Session):
        self.db = db

    # ---- Manufacturer CRUD -------------------------------------------------

    def list_manufacturers(self, organization_id: uuid.UUID) -> List[ManufacturerResponse]:
        stmt = select(Manufacturer).where(
            or_(Manufacturer.is_global == True, Manufacturer.organization_id == organization_id)  # noqa: E712
        ).order_by(Manufacturer.name.asc())
        rows = self.db.execute(stmt).scalars().all()
        return [ManufacturerResponse.model_validate(r) for r in rows]

    def _get_visible(self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID) -> Manufacturer:
        """Fetches a manufacturer only if visible to this org; otherwise 404
        (never 403) so a guessed ID from another tenant reveals nothing."""
        stmt = select(Manufacturer).where(
            Manufacturer.id == manufacturer_id,
            or_(Manufacturer.is_global == True, Manufacturer.organization_id == organization_id),  # noqa: E712
        )
        mfr = self.db.execute(stmt).scalar_one_or_none()
        if not mfr:
            raise ResourceNotFoundError("Manufacturer not found")
        return mfr

    def _get_owned(self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID) -> Manufacturer:
        """Fetches a manufacturer only if this org can WRITE to it — global
        entries are read-only to every tenant, so writes require exact
        organization ownership, not just visibility."""
        mfr = self._get_visible(manufacturer_id, organization_id)
        if mfr.is_global or mfr.organization_id != organization_id:
            raise BusinessLogicError("Global manufacturer entries are read-only")
        return mfr

    def create_manufacturer(self, organization_id: uuid.UUID, data: ManufacturerCreate, actor_id: Optional[uuid.UUID]) -> ManufacturerResponse:
        mfr = Manufacturer(
            id=uuid.uuid4(), organization_id=organization_id, name=data.name.strip(),
            is_global=False, created_by=actor_id, updated_by=actor_id,
        )
        self.db.add(mfr)
        self.db.commit()
        self.db.refresh(mfr)
        return ManufacturerResponse.model_validate(mfr)

    def update_manufacturer(self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID, data: ManufacturerUpdate, actor_id: Optional[uuid.UUID]) -> ManufacturerResponse:
        mfr = self._get_owned(manufacturer_id, organization_id)
        if data.name is not None:
            mfr.name = data.name.strip()
        mfr.updated_by = actor_id
        self.db.commit()
        self.db.refresh(mfr)
        return ManufacturerResponse.model_validate(mfr)

    # ---- Dictionary CRUD ----------------------------------------------------

    def list_codes(
        self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID,
        search: Optional[str] = None, category: Optional[ItemCategory] = None,
    ) -> List[ManufacturerCodeResponse]:
        self._get_visible(manufacturer_id, organization_id)  # 404s if not visible
        stmt = select(ManufacturerCodeDictionary).where(ManufacturerCodeDictionary.manufacturer_id == manufacturer_id)
        if category:
            stmt = stmt.where(ManufacturerCodeDictionary.category == category)
        if search:
            like = f"%{search.strip().upper()}%"
            stmt = stmt.where(or_(
                ManufacturerCodeDictionary.normalized_code.ilike(like),
                ManufacturerCodeDictionary.description.ilike(like),
            ))
        stmt = stmt.order_by(ManufacturerCodeDictionary.code.asc())
        rows = self.db.execute(stmt).scalars().all()
        return [ManufacturerCodeResponse.model_validate(r) for r in rows]

    def create_code(self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID, data: ManufacturerCodeCreate, actor_id: Optional[uuid.UUID]) -> ManufacturerCodeResponse:
        self._get_owned(manufacturer_id, organization_id)
        normalized = normalize_sku(data.code)
        if not normalized:
            raise BusinessLogicError("Code cannot be empty")
        existing = self.db.execute(select(ManufacturerCodeDictionary).where(
            ManufacturerCodeDictionary.manufacturer_id == manufacturer_id,
            ManufacturerCodeDictionary.normalized_code == normalized,
        )).scalar_one_or_none()
        if existing:
            raise BusinessLogicError(f"Code '{data.code}' already exists for this manufacturer")

        row = ManufacturerCodeDictionary(
            id=uuid.uuid4(), manufacturer_id=manufacturer_id,
            code=data.code, normalized_code=normalized, category=data.category,
            description=data.description, alias_group=data.alias_group,
            is_primary_alias=data.is_primary_alias, is_current=data.is_current,
            source_version=data.source_version, effective_from=data.effective_from,
            effective_to=data.effective_to, created_by=actor_id, updated_by=actor_id,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise BusinessLogicError(f"Code '{data.code}' already exists for this manufacturer")
        self.db.refresh(row)
        return ManufacturerCodeResponse.model_validate(row)

    def _get_code_owned(self, manufacturer_id: uuid.UUID, code_id: uuid.UUID, organization_id: uuid.UUID) -> ManufacturerCodeDictionary:
        self._get_owned(manufacturer_id, organization_id)
        row = self.db.execute(select(ManufacturerCodeDictionary).where(
            ManufacturerCodeDictionary.id == code_id,
            ManufacturerCodeDictionary.manufacturer_id == manufacturer_id,
        )).scalar_one_or_none()
        if not row:
            raise ResourceNotFoundError("Dictionary entry not found")
        return row

    def update_code(self, manufacturer_id: uuid.UUID, code_id: uuid.UUID, organization_id: uuid.UUID, data: ManufacturerCodeUpdate, actor_id: Optional[uuid.UUID]) -> ManufacturerCodeResponse:
        row = self._get_code_owned(manufacturer_id, code_id, organization_id)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(row, field, value)
        row.updated_by = actor_id
        self.db.commit()
        self.db.refresh(row)
        return ManufacturerCodeResponse.model_validate(row)

    def deactivate_code(self, manufacturer_id: uuid.UUID, code_id: uuid.UUID, organization_id: uuid.UUID, actor_id: Optional[uuid.UUID]) -> ManufacturerCodeResponse:
        row = self._get_code_owned(manufacturer_id, code_id, organization_id)
        row.is_current = False
        row.updated_by = actor_id
        self.db.commit()
        self.db.refresh(row)
        return ManufacturerCodeResponse.model_validate(row)

    def delete_code(self, manufacturer_id: uuid.UUID, code_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        # Safe to hard-delete: a dictionary row is a lookup entry, not
        # extraction history — every past classification decision that used
        # it is already immutably snapshotted on CanonicalLineItem.cabinet_classification,
        # so deleting the dictionary row cannot corrupt or rewrite prior evidence.
        row = self._get_code_owned(manufacturer_id, code_id, organization_id)
        self.db.delete(row)
        self.db.commit()

    # ---- Bulk import ---------------------------------------------------------

    def _parse_rows(self, filename: str, content: bytes) -> List[dict]:
        lower = filename.lower()
        if lower.endswith(".csv"):
            text = content.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            return [dict(row) for row in reader]
        if lower.endswith(".xlsx"):
            if not openpyxl:
                raise BusinessLogicError("Excel import is unavailable on this server")
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            headers = [str(h).strip().lower() if h is not None else "" for h in next(rows_iter, [])]
            out = []
            for values in rows_iter:
                if values is None or all(v is None for v in values):
                    continue
                out.append({headers[i]: values[i] for i in range(min(len(headers), len(values)))})
            return out
        raise BusinessLogicError("Unsupported file type — use .csv or .xlsx")

    def _validate_rows(self, manufacturer_id: uuid.UUID, rows: List[dict]) -> Tuple[List[dict], List[BulkImportRowError], int]:
        """Returns (valid_rows_ready_to_insert, errors, duplicate_count).
        Never mutates the database — pure validation, safe to call from both
        preview and commit so they can never disagree."""
        existing_codes = {
            r.normalized_code for r in self.db.execute(
                select(ManufacturerCodeDictionary.normalized_code).where(ManufacturerCodeDictionary.manufacturer_id == manufacturer_id)
            ).all()
        }
        seen_in_file = set()
        valid_rows: List[dict] = []
        errors: List[BulkImportRowError] = []
        duplicate_count = 0

        for idx, raw in enumerate(rows, start=2):  # header is row 1
            code = str(raw.get("code") or "").strip()
            if not code:
                errors.append(BulkImportRowError(row=idx, code=None, reason="code is required"))
                continue
            normalized = normalize_sku(code)
            if not normalized:
                errors.append(BulkImportRowError(row=idx, code=code, reason="code normalizes to empty"))
                continue

            category_raw = str(raw.get("category") or "").strip().upper()
            try:
                category = ItemCategory(category_raw)
            except ValueError:
                errors.append(BulkImportRowError(row=idx, code=code, reason=f"invalid category '{category_raw}'"))
                continue

            if normalized in existing_codes or normalized in seen_in_file:
                duplicate_count += 1
                continue
            seen_in_file.add(normalized)

            is_current_raw = str(raw.get("is_current", "")).strip().lower()
            is_current = True if is_current_raw == "" else is_current_raw in _TRUE_STRINGS

            def _parse_date(val):
                if not val:
                    return None
                if isinstance(val, datetime):
                    return val
                try:
                    return datetime.fromisoformat(str(val).strip())
                except ValueError:
                    return None

            valid_rows.append({
                "code": code,
                "normalized_code": normalized,
                "description": (str(raw.get("description")).strip() if raw.get("description") else None),
                "category": category,
                "alias_group": (str(raw.get("alias_group")).strip() if raw.get("alias_group") else None),
                "is_current": is_current,
                "source_version": (str(raw.get("source_version")).strip() if raw.get("source_version") else None),
                "effective_from": _parse_date(raw.get("effective_from")),
                "effective_to": _parse_date(raw.get("effective_to")),
            })

        return valid_rows, errors, duplicate_count

    def _check_import_size(self, content: bytes) -> None:
        if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise BusinessLogicError("File too large")

    def preview_import(self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID, filename: str, content: bytes) -> BulkImportPreview:
        self._get_owned(manufacturer_id, organization_id)
        self._check_import_size(content)
        rows = self._parse_rows(filename, content)
        valid_rows, errors, duplicate_count = self._validate_rows(manufacturer_id, rows)
        return BulkImportPreview(
            total_rows=len(rows), valid=len(valid_rows), duplicates=duplicate_count,
            invalid=len(errors), errors=errors[:50],
        )

    def commit_import(self, manufacturer_id: uuid.UUID, organization_id: uuid.UUID, filename: str, content: bytes, actor_id: Optional[uuid.UUID]) -> BulkImportResult:
        self._get_owned(manufacturer_id, organization_id)
        self._check_import_size(content)
        rows = self._parse_rows(filename, content)
        valid_rows, errors, duplicate_count = self._validate_rows(manufacturer_id, rows)

        # Transaction-based: either every valid row is inserted, or none are
        # (a mid-batch DB error rolls back the whole import — it never leaves
        # the dictionary half-imported).
        try:
            for row in valid_rows:
                self.db.add(ManufacturerCodeDictionary(
                    id=uuid.uuid4(), manufacturer_id=manufacturer_id, created_by=actor_id, updated_by=actor_id,
                    **row,
                ))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise BusinessLogicError("Import failed — no rows were committed")

        return BulkImportResult(
            imported=len(valid_rows), skipped_duplicates=duplicate_count,
            skipped_invalid=len(errors), errors=errors[:50],
        )
