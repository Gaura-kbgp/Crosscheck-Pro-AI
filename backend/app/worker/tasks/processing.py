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
from app.engines.classification import ItemClassifier
from app.engines.extraction_validator import ExtractionValidator
import json
import uuid


def _get_db():
    """Get a fresh DB session."""
    return SessionLocal()


def _update_job_status(job_id, status, error=None, project_id=None):
    """Update job status with a fresh DB connection."""
    db = _get_db()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if job:
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


def _run_pipeline(job_id_str: str, project_id_str: str, organization_id_str: str, correlation_id: str):
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

        # Cleanup old processing data (if retrying)
        db.query(CanonicalLineItem).filter(CanonicalLineItem.project_id == project_id).delete()
        db.query(MatchGroup).filter(MatchGroup.project_id == project_id).delete()
        db.query(Discrepancy).filter(Discrepancy.project_id == project_id).delete()
        db.query(Extraction).filter(Extraction.document_id.in_(doc_ids)).delete()
        db.commit()
    finally:
        db.close()

    # ── Stage 2: Extraction ──
    _update_job_status(job_id, ProcessingJobStatus.EXTRACTING, project_id=project_id)
    
    from app.integrations.storage import StorageService
    storage_service = StorageService()
    ai = get_ai_provider()
    
    for doc in doc_info:
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
            try:
                raw_data = ai.extract_structured_data(file_bytes, doc["mime_type"], prompt, schema)
                
                # Save extraction with fresh DB connection
                db = _get_db()
                try:
                    ext = Extraction(
                        document_id=doc["id"],
                        organization_id=organization_id,
                        raw_data=raw_data,
                        provider=getattr(ai, "provider_name", "openai"),
                        model_name=getattr(ai, "model_name", "gpt-4o"),
                        prompt_version="v1"
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
    _update_job_status(job_id, ProcessingJobStatus.NORMALIZING, project_id=project_id)
    
    db = _get_db()
    try:
        extractions = db.query(Extraction).filter(
            Extraction.document_id.in_(doc_ids)
        ).all()
        
        classifier = ItemClassifier()
        validator = ExtractionValidator()

        for ext in extractions:
            doc = next((d for d in doc_info if d["id"] == ext.document_id), None)
            if not doc:
                continue
                
            items = ext.raw_data.get("items", [])
            for item in items:
                # 1. Extraction evidence validation
                _, _, validation_meta = validator.validate_item(item, doc["document_type"])

                # 2. Classification
                classification = classifier.classify(
                    raw_sku=item.get("sku"),
                    description=item.get("description"),
                    dimensions=item.get("dimensions"),
                    modifications=item.get("modifications"),
                    source_type=doc["document_type"]
                )

                canonical = CanonicalLineItem(
                    project_id=project_id,
                    organization_id=organization_id,
                    document_id=doc["id"],
                    source_type=doc["document_type"],
                    raw_sku=item.get("sku"),
                    normalized_sku=normalize_sku(item.get("sku")),
                    description=item.get("description"),
                    item_category=classification.category,
                    category_confidence=classification.confidence,
                    category_evidence=classification.to_dict(),
                    quantity=normalize_quantity(item.get("quantity")),
                    dimensions=parse_and_normalize_dimensions(item.get("dimensions")),
                    price=item.get("price"),
                    notes=item.get("notes")
                )

                source_meta = {"validation": validation_meta}
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
    _update_job_status(job_id, ProcessingJobStatus.COMPLETED, project_id=project_id)


@shared_task(bind=True, max_retries=3)
def process_project_pipeline(self, job_id_str: str, project_id_str: str, organization_id_str: str, correlation_id: str):
    try:
        _run_pipeline(job_id_str, project_id_str, organization_id_str, correlation_id)
    except Exception as exc:
        try:
            self.retry(exc=exc, countdown=2 ** self.request.retries)
        except self.MaxRetriesExceededError:
            _update_job_status(uuid.UUID(job_id_str), ProcessingJobStatus.FAILED, {"message": "Max retries exceeded"}, project_id=uuid.UUID(project_id_str))

def process_project_pipeline_sync(job_id_str: str, project_id_str: str, organization_id_str: str, correlation_id: str):
    try:
        _run_pipeline(job_id_str, project_id_str, organization_id_str, correlation_id)
    except Exception as exc:
        _update_job_status(uuid.UUID(job_id_str), ProcessingJobStatus.FAILED, {"message": str(exc)}, project_id=uuid.UUID(project_id_str))
