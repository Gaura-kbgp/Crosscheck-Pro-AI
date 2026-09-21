from celery import shared_task
import uuid
import structlog
from app.db.session import SessionLocal
from app.services.report_service import ReportService

logger = structlog.get_logger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def generate_report_task(self, report_id_str: str):
    """
    Asynchronous Celery task for generating PDF/CSV reports.
    """
    logger.info("Starting report generation task", report_id=report_id_str)
    report_id = uuid.UUID(report_id_str)
    db = SessionLocal()
    try:
        service = ReportService(db)
        service.process_report_job(report_id)
        logger.info("Report generation task completed successfully", report_id=report_id_str)
    except Exception as exc:
        logger.error("Report generation task failed", report_id=report_id_str, error=str(exc))
        try:
            # Retry with exponential backoff if celery task
            raise self.retry(exc=exc)
        except Exception:
            # If max retries exceeded, let it settle with FAILED status recorded by service
            pass
    finally:
        db.close()
