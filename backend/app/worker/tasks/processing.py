from celery import shared_task
from app.db.session import SessionLocal
from app.models.core import (
    ProcessingJob, ProcessingJobStatus, Document, Extraction,
    CanonicalLineItem, MatchGroup, Discrepancy, Project, ProjectStatus
)
from app.integrations.ai import get_ai_provider
from app.schemas.extraction import DesignExtraction, OrderExtraction, AcknowledgementExtraction
from app.integrations.ai.prompts.design_v1 import DESIGN_PROMPT_V1
from app.integrations.ai.prompts.order_v1 import ORDER_PROMPT_V1
from app.integrations.ai.prompts.acknowledgement_v1 import ACKNOWLEDGEMENT_PROMPT_V1
from app.engines.normalization import normalize_sku, parse_and_normalize_dimensions, normalize_quantity
from app.engines.cabinet_intelligence import CabinetCodeIntelligence
from app.engines.extraction_validator import ExtractionValidator
import json
import uuid

# F8.3 Phase 3 §23: bumped whenever extraction behavior changes materially
# (new prompt safety rules, page evidence, OCR/reconciliation, etc). Combined
# with document_hash + provider + model + prompt_version, this is the
# identity used to decide whether a prior extraction can be safely reused.
EXTRACTION_VERSION = "f8.3.3"


def _get_db():
    """Get a fresh DB session."""
    return SessionLocal()


def _is_cancelled(job_id) -> bool:
    """Checks whether the job was cancelled (marked FAILED) by the user since the pipeline started."""
    db = _get_db()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        return bool(job and job.status == ProcessingJobStatus.FAILED)
    finally:
        db.close()


def _update_job_status(job_id, status, error=None, project_id=None):
    """Update job status with a fresh DB connection.

    Never regresses a job out of a terminal state (COMPLETED/FAILED) into an
    active stage: a cancellation can race with the pipeline's own stage
    transitions, and the terminal state set by cancel must win.
    """
    db = _get_db()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
            already_terminal = job.status in (ProcessingJobStatus.COMPLETED, ProcessingJobStatus.FAILED)
            target_is_terminal = status in (ProcessingJobStatus.COMPLETED, ProcessingJobStatus.FAILED)
            if already_terminal and not target_is_terminal:
                return
            job.status = status
            if error:
                job.error = error
        if project_id:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                if status == ProcessingJobStatus.COMPLETED:
                    project.status = ProjectStatus.REVIEW_REQUIRED
                elif status == ProcessingJobStatus.FAILED:
                    project.status = ProjectStatus.FAILED
                elif status in [ProcessingJobStatus.VALIDATING, ProcessingJobStatus.EXTRACTING, ProcessingJobStatus.NORMALIZING, ProcessingJobStatus.MATCHING, ProcessingJobStatus.COMPARING, ProcessingJobStatus.GENERATING_DISCREPANCIES]:
                    project.status = ProjectStatus.PROCESSING
        db.commit()
    finally:
        db.close()


def _run_pipeline(job_id_str: str, project_id_str: str, organization_id_str: str, correlation_id: str, force_reprocess: bool = False):
    job_id = uuid.UUID(job_id_str)
    project_id = uuid.UUID(project_id_str)
    organization_id = uuid.UUID(organization_id_str)
    
    # ── Stage 1: Validation ──
    _update_job_status(job_id, ProcessingJobStatus.VALIDATING, project_id=project_id)
    
    db = _get_db()
    try:
        docs = db.query(Document).filter(
            Document.project_id == project_id,
            Document.organization_id == organization_id
        ).all()

        if not docs:
            _update_job_status(job_id, ProcessingJobStatus.FAILED, {"message": "No documents found"}, project_id=project_id)
            return

        # Cabinet Code Intelligence: nullable on every existing project, so a
        # project with no manufacturer configured falls through to the
        # existing generic classifier completely unchanged (backward compat).
        project_row = db.query(Project).filter(Project.id == project_id).first()
        manufacturer_id = project_row.manufacturer_id if project_row else None

        # Collect doc info before closing DB
        doc_info = []
        for d in docs:
            doc_info.append({
                "id": d.id,
                "document_type": d.document_type.value,
                "storage_path": d.storage_path,
                "mime_type": d.mime_type,
            })
        doc_ids = [d.id for d in docs]

        # Cleanup old CrossCheck data (if retrying) — these are always fully
        # regenerated from the latest extraction each run, so clearing them is
        # safe and keeps Celery retries from creating duplicates (§28).
        # Extraction rows are deliberately NOT deleted here (F8.3 Phase 3 §27):
        # each attempt is preserved as its own row; Stage 2 below marks the
        # newest one is_latest=True instead of destroying prior history.
        db.query(CanonicalLineItem).filter(CanonicalLineItem.project_id == project_id).delete()
        db.query(MatchGroup).filter(MatchGroup.project_id == project_id).delete()
        db.query(Discrepancy).filter(Discrepancy.project_id == project_id).delete()
        doc_hashes = {d.id: d.document_hash for d in docs}
        db.commit()
    finally:
        db.close()

    # ── Stage 2: Extraction ──
    _update_job_status(job_id, ProcessingJobStatus.EXTRACTING, project_id=project_id)
    
    from app.integrations.storage import StorageService
    storage_service = StorageService()
    ai = get_ai_provider()
    doc_validator = ExtractionValidator()
    extraction_warnings = []  # F8.3: document-level completeness warnings, surfaced on job completion

    for doc in doc_info:
        # Stop advancing the pipeline if the user cancelled the job
        if _is_cancelled(job_id):
            return

        # Download file from storage (no DB needed)
        try:
            file_bytes = storage_service.get_file(doc["storage_path"])
        except Exception as e:
            _update_job_status(job_id, ProcessingJobStatus.FAILED, {
                "message": f"Failed to download document {doc['id']}", 
                "details": str(e)
            }, project_id=project_id)
            return
        
        # Determine prompt and schema
        prompt = ""
        schema = None
        if doc["document_type"] == "DESIGN":
            prompt = DESIGN_PROMPT_V1
            schema = DesignExtraction
        elif doc["document_type"] == "ORDER":
            prompt = ORDER_PROMPT_V1
            schema = OrderExtraction
        elif doc["document_type"] == "ACKNOWLEDGEMENT":
            prompt = ACKNOWLEDGEMENT_PROMPT_V1
            schema = AcknowledgementExtraction
            
        if prompt and schema:
            provider_name = getattr(ai, "provider_name", "openai")
            model_name = getattr(ai, "model_name", "gpt-4o")
            current_hash = doc_hashes.get(doc["id"])

            # F8.3 Phase 3 §24: idempotency — reuse a prior COMPLETED extraction
            # attempt for this exact document content + extraction identity
            # instead of re-calling the AI, UNLESS force_reprocess is set or the
            # identity has changed (§25/§26 — never freeze a bad result forever;
            # a version/prompt/model/provider bump always triggers fresh work).
            reused_extraction = None
            db = _get_db()
            try:
                if not force_reprocess and current_hash:
                    latest = db.query(Extraction).filter(
                        Extraction.document_id == doc["id"],
                        Extraction.is_latest == True,  # noqa: E712
                    ).first()
                    if (latest and latest.document_hash == current_hash
                            and latest.extraction_version == EXTRACTION_VERSION
                            and latest.provider == provider_name
                            and latest.model_name == model_name
                            and latest.prompt_version == "v1"):
                        reused_extraction = latest
                max_attempt = db.query(Extraction).filter(Extraction.document_id == doc["id"]).count()
            finally:
                db.close()

            if reused_extraction is not None:
                # Nothing re-extracted; downstream stages read this document's
                # is_latest row exactly as if it had just been written. Surface
                # the reused attempt's own prior validation status too, so the
                # completion warning banner stays accurate.
                prior_validation = reused_extraction.confidence or {}
                if prior_validation.get("status") == "UNCERTAIN":
                    extraction_warnings.append({
                        "document_id": str(doc["id"]),
                        "document_type": doc["document_type"],
                        "reused_from_attempt": reused_extraction.attempt,
                        **prior_validation,
                    })
                continue

            try:
                raw_data = ai.extract_structured_data(
                    file_bytes, doc["mime_type"], prompt, schema, doc_type=doc.get("document_type")
                )

                # F8.3 Phase 2/3: page evidence is used HERE, transiently, to verify
                # each item's self-reported page_number/source_text against the real,
                # deterministically-extracted page text — then dropped rather than
                # persisted in full (bounded storage; see extraction_validator docstring).
                # Every item gets an evidence_status annotation; the item itself is
                # never dropped or mutated beyond that.
                page_evidence = raw_data.pop("_page_evidence", [])
                for item in raw_data.get("items", []):
                    if "verification" in item:
                        # F8.3 Phase 3: this item already went through OCR/Vision
                        # reconciliation (app/engines/reconciliation.py) — that is a
                        # stronger, two-independent-source verification than the
                        # single-source page-text check below, so it is not re-derived
                        # or overwritten here.
                        continue
                    evidence_status, evidence_issues = doc_validator.validate_evidence(item, page_evidence)
                    item["evidence_status"] = evidence_status
                    if evidence_issues:
                        item["evidence_issues"] = [i.to_dict() for i in evidence_issues]

                # F8.3 Phase 1: document-level completeness validation (empty extraction,
                # line-number gaps) — never blocks the pipeline, only records signal.
                doc_validation = doc_validator.validate_document(raw_data.get("items", []), doc["document_type"])
                doc_validation["page_evidence"] = doc_validator.summarize_page_evidence(page_evidence)
                # F8.3 Phase 3 §18: a critical OCR page failure must never be
                # silently absorbed into an otherwise-VALID document status.
                if doc_validator.has_critical_ocr_failure(page_evidence):
                    doc_validation["status"] = "UNCERTAIN"
                if doc_validation["status"] == "UNCERTAIN":
                    extraction_warnings.append({
                        "document_id": str(doc["id"]),
                        "document_type": doc["document_type"],
                        **doc_validation,
                    })

                # Save extraction with fresh DB connection. F8.3 Phase 3 §27:
                # prior attempts for this document are marked is_latest=False,
                # never deleted — a new row is always appended.
                db = _get_db()
                try:
                    db.query(Extraction).filter(Extraction.document_id == doc["id"]).update({"is_latest": False})
                    ext = Extraction(
                        document_id=doc["id"],
                        organization_id=organization_id,
                        raw_data=raw_data,
                        provider=provider_name,
                        model_name=model_name,
                        prompt_version="v1",
                        confidence=doc_validation,
                        attempt=max_attempt + 1,
                        is_latest=True,
                        extraction_version=EXTRACTION_VERSION,
                        document_hash=current_hash,
                    )
                    db.add(ext)
                    db.commit()
                finally:
                    db.close()
            except Exception as e:
                _update_job_status(job_id, ProcessingJobStatus.FAILED, {
                    "message": f"Extraction failed for document {doc['id']}", 
                    "details": str(e)
                }, project_id=project_id)
                return
    
    # ── Stage 3: Normalization ──
    if _is_cancelled(job_id):
        return
    _update_job_status(job_id, ProcessingJobStatus.NORMALIZING, project_id=project_id)
    
    db = _get_db()
    try:
        # F8.3 Phase 3: Extraction is now one-row-per-attempt (history-preserving),
        # so normalization must read only each document's current attempt.
        extractions = db.query(Extraction).filter(
            Extraction.document_id.in_(doc_ids),
            Extraction.is_latest == True,  # noqa: E712
        ).all()
        
        validator = ExtractionValidator()
        # Cabinet Code Intelligence: one instance per run so the manufacturer
        # dictionary loads once (§37), not per item. When manufacturer_id is
        # None, its dictionary is unconfigured and every analyze_candidate()
        # call falls straight through to the same ItemClassifier used before
        # this feature existed, with identical arguments — item_category and
        # category_confidence are therefore byte-identical to pre-Cabinet-
        # Code-Intelligence behavior for every project with no manufacturer
        # configured.
        cabinet_intel = CabinetCodeIntelligence(db, manufacturer_id=manufacturer_id)

        for ext in extractions:
            doc = next((d for d in doc_info if d["id"] == ext.document_id), None)
            if not doc:
                continue

            items = ext.raw_data.get("items", [])
            for item in items:
                # 1. Extraction evidence validation
                _, _, validation_meta = validator.validate_item(item, doc["document_type"])

                # 2. Cabinet Code Intelligence classification — manufacturer-
                # dictionary-first, falling through to the unmodified generic
                # ItemClassifier when no manufacturer match exists. An
                # unresolved OCR/Vision SKU conflict (Phase 3.1 reconciliation,
                # untouched here) is passed through as extra evidence so it
                # can never present as a confident classification (§35).
                verification = item.get("verification")
                conflict_skus = [
                    c.get("ocr_value") if c.get("ocr_value") != item.get("sku") else c.get("vision_value")
                    for c in (verification or {}).get("conflicts", [])
                    if c.get("field") == "sku"
                ]
                classification = cabinet_intel.analyze_candidate(
                    raw_sku=item.get("sku"),
                    description=item.get("description"),
                    dimensions=item.get("dimensions"),
                    modifications=item.get("modifications"),
                    quantity=item.get("quantity"),
                    source_type=doc["document_type"],
                    page_number=item.get("page_number"),
                    source_text=item.get("source_text"),
                    reconciliation_verification=verification,
                    candidate_skus=[s for s in conflict_skus if s],
                )

                canonical = CanonicalLineItem(
                    project_id=project_id,
                    organization_id=organization_id,
                    document_id=doc["id"],
                    source_type=doc["document_type"],
                    raw_sku=item.get("sku"),
                    normalized_sku=normalize_sku(item.get("sku")),
                    description=item.get("description"),
                    item_category=classification.classification,
                    category_confidence=classification.confidence_score,
                    category_evidence=classification.evidence,
                    cabinet_classification=classification.to_dict(),
                    quantity=normalize_quantity(item.get("quantity")),
                    dimensions=parse_and_normalize_dimensions(item.get("dimensions")),
                    price=item.get("price"),
                    notes=item.get("notes")
                )

                # F8.3 Phase 2: item-level source evidence, immutable once written —
                # never overwritten by normalization (normalized_sku above is a
                # separate field; raw_sku and this evidence block always keep the
                # original extraction's claim, verified or not).
                source_meta = {
                    "validation": validation_meta,
                    "evidence": {
                        "page_number": item.get("page_number"),
                        "source_text": item.get("source_text"),
                        "status": item.get("evidence_status", "UNCERTAIN"),
                        "issues": item.get("evidence_issues", []),
                        # F8.3 Phase 3: present only for OCR+Vision-reconciled items;
                        # {method, status, conflicts?} — conflicts preserve BOTH
                        # sources' raw values, never overwritten with a guess.
                        "verification": item.get("verification"),
                    },
                }
                if doc["document_type"] == "DESIGN":
                    canonical.finish = item.get("finish")
                    canonical.door_style = item.get("door_style")
                    canonical.modifications = item.get("modifications")
                    canonical.source_metadata = source_meta
                elif doc["document_type"] == "ORDER":
                    canonical.finish = item.get("finish")
                    canonical.door_style = item.get("door_style")
                    canonical.modifications = item.get("modifications")
                    source_meta["line_number"] = item.get("line_number")
                    canonical.source_metadata = source_meta
                elif doc["document_type"] == "ACKNOWLEDGEMENT":
                    canonical.acknowledgement_status = item.get("ack_status")
                    canonical.substitution_sku = item.get("substitution_sku")
                    canonical.rejection_reason = item.get("rejection_reason")
                    canonical.backorder = item.get("backorder")
                    canonical.changed_item = item.get("changed_item")
                    canonical.manufacturer_reference = item.get("manufacturer_reference")
                    canonical.source_metadata = source_meta
                
                db.add(canonical)
        
        db.commit()
    finally:
        db.close()
    
    # ── Stage 4: Matching ──
    if _is_cancelled(job_id):
        return
    _update_job_status(job_id, ProcessingJobStatus.MATCHING, project_id=project_id)
    
    db = _get_db()
    try:
        all_canonical_items = db.query(CanonicalLineItem).filter(
            CanonicalLineItem.project_id == project_id
        ).all()
        
        design_items = [i for i in all_canonical_items if i.source_type.value == "DESIGN"]
        order_items = [i for i in all_canonical_items if i.source_type.value == "ORDER"]
        ack_items = [i for i in all_canonical_items if i.source_type.value == "ACKNOWLEDGEMENT"]
        
        from app.engines.matching import MatchingEngine
        matching_engine = MatchingEngine()
        match_groups = matching_engine.match_items(design_items, order_items, ack_items, project_id, organization_id)
        
        for mg in match_groups:
            db.add(mg)
        db.flush()

        # ── Stage 5: Comparing & Discrepancies ──
        _update_job_status(job_id, ProcessingJobStatus.COMPARING, project_id=project_id)
        _update_job_status(job_id, ProcessingJobStatus.GENERATING_DISCREPANCIES, project_id=project_id)

        from app.engines.crosscheck import CrossCheckEngine
        crosscheck_engine = CrossCheckEngine()
        discrepancies = crosscheck_engine.evaluate(match_groups, project_id, organization_id)
        
        for d in discrepancies:
            db.add(d)
            
        db.commit()
    finally:
        db.close()

    # ── Stage 6: Completed ──
    if _is_cancelled(job_id):
        return
    # F8.3: surface document-level extraction warnings non-fatally — the job
    # still completes (matching/cross-check ran on real data), but Human
    # Review and the project UI can show "extraction could not be fully
    # verified" for the flagged document(s) rather than staying silent.
    completion_error = {"warnings": extraction_warnings} if extraction_warnings else None
    _update_job_status(job_id, ProcessingJobStatus.COMPLETED, completion_error, project_id=project_id)


@shared_task(bind=True, max_retries=3)
def process_project_pipeline(self, job_id_str: str, project_id_str: str, organization_id_str: str, correlation_id: str, force_reprocess: bool = False):
    try:
        _run_pipeline(job_id_str, project_id_str, organization_id_str, correlation_id, force_reprocess=force_reprocess)
    except Exception as exc:
        try:
            self.retry(exc=exc, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            _update_job_status(uuid.UUID(job_id_str), ProcessingJobStatus.FAILED, {"message": "Max retries exceeded"}, project_id=uuid.UUID(project_id_str))

def process_project_pipeline_sync(job_id_str: str, project_id_str: str, organization_id_str: str, correlation_id: str, force_reprocess: bool = False):
    try:
        _run_pipeline(job_id_str, project_id_str, organization_id_str, correlation_id, force_reprocess=force_reprocess)
    except Exception as exc:
        _update_job_status(uuid.UUID(job_id_str), ProcessingJobStatus.FAILED, {"message": str(exc)}, project_id=uuid.UUID(project_id_str))
