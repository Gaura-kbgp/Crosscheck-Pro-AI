"""
Cabinet Code Intelligence — manufacturer code dictionary lookup.

Loads a manufacturer's current code entries ONCE per document-processing run
(never per item — §37 performance requirement) and answers exact/alias
lookups from the in-memory index. A manufacturer with no dictionary entries
(the common case today, since no import tooling exists yet) behaves exactly
like "no manufacturer configured": every lookup misses, and
CabinetCodeIntelligence falls through to the existing generic classifier.
"""
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.core import ManufacturerCodeDictionary
from app.engines.normalization import normalize_sku


class ManufacturerCodeDictionaryLookup:
    def __init__(self, db: Session, manufacturer_id: Optional[UUID]):
        self.manufacturer_id = manufacturer_id
        self._by_code: Dict[str, ManufacturerCodeDictionary] = {}
        self._by_alias_group: Dict[str, List[ManufacturerCodeDictionary]] = {}

        if not manufacturer_id:
            return

        rows = (
            db.query(ManufacturerCodeDictionary)
            .filter(
                ManufacturerCodeDictionary.manufacturer_id == manufacturer_id,
                ManufacturerCodeDictionary.is_current == True,  # noqa: E712
            )
            .all()
        )
        for row in rows:
            key = row.normalized_code or normalize_sku(row.code)
            if not key:
                continue
            # A normalized code should map to exactly one dictionary entry;
            # if data entry ever duplicates a code, the first row wins and
            # this is intentionally NOT treated as a lookup failure — the
            # dictionary is expected to be curated, not attacker-controlled.
            self._by_code.setdefault(key, row)
            if row.alias_group:
                self._by_alias_group.setdefault(row.alias_group, []).append(row)

    @property
    def is_configured(self) -> bool:
        return bool(self.manufacturer_id)

    def exact_match(self, normalized_code: Optional[str]) -> Optional[ManufacturerCodeDictionary]:
        if not normalized_code:
            return None
        return self._by_code.get(normalized_code)

    def alias_siblings(self, entry: ManufacturerCodeDictionary) -> List[str]:
        """All other known spellings sharing this entry's alias group (for candidate_variants)."""
        if not entry.alias_group:
            return []
        return [r.code for r in self._by_alias_group.get(entry.alias_group, []) if r.id != entry.id]
