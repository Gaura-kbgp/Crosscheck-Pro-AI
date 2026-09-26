import io
import csv
import json
import uuid
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

from app.models.core import (
    Project, Document, MatchGroup, Discrepancy, HumanReview, AuditLog,
    Report, ReportFormat, ReportStatus, ProjectStatus, Severity, MatchGroupStatus
)
from app.repositories.report_repository import ReportRepository
from app.integrations.storage import StorageService
from app.core.exceptions import ResourceNotFoundError, BusinessLogicError
from app.engines.crosscheck import _get_item_qty


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas for ReportLab to dynamically calculate and render 'Page X of Y' footers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header rule & title (on pages after first)
        if self._pageNumber > 1:
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(36, 756, 576, 756)
            self.drawString(36, 762, "CrossCheckPro™ — Cross-Check & Verification Report")

        # Footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 42, 576, 42)
        
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.drawString(36, 30, f"Generated: {timestamp_str} | Confidential — For Internal Organization Use Only")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 30, page_text)
        self.restoreState()


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ReportRepository(db)
        self.storage_service = StorageService()

    def create_report(
        self,
        project_id: uuid.UUID,
        organization_id: uuid.UUID,
        format: ReportFormat = ReportFormat.PDF,
        background_tasks: Any = None
    ) -> Report:
        # 1. Verify project exists & belongs to org
        project = self.db.scalars(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id
            )
        ).first()
        if not project:
            raise ResourceNotFoundError(message="Project not found")

        # 2. Idempotency check: if an active report (QUEUED or GENERATING) exists for the same format, reuse it
        active_report = self.repository.get_active_report_for_project(project_id, organization_id, format)
        if active_report:
            return active_report

        # 3. Create report entry in database
        report = self.repository.create(
            project_id=project_id,
            organization_id=organization_id,
            format=format,
            status=ReportStatus.QUEUED
        )

        # 4. Dispatch task via BackgroundTasks or fallback
        if background_tasks:
            from app.db.session import SessionLocal
            def _generate_sync(rep_id):
                try:
                    fresh_db = SessionLocal()
                    try:
                        srv = ReportService(fresh_db)
                        srv.process_report_job(rep_id)
                    finally:
                        fresh_db.close()
                except Exception:
                    pass
            background_tasks.add_task(_generate_sync, report.id)
        else:
            try:
                from app.worker.tasks.reporting import generate_report_task
                generate_report_task.delay(str(report.id))
            except Exception:
                # Fallback synchronous generation
                try:
                    self.process_report_job(report.id)
                except Exception:
                    pass

        return report

    def get_report(self, report_id: uuid.UUID, organization_id: uuid.UUID) -> Report:
        report = self.repository.get_by_id_and_org(report_id, organization_id)
        if not report:
            raise ResourceNotFoundError(message="Report not found")
        
        # Attach signed download url if completed
        if report.status == ReportStatus.COMPLETED and report.storage_path:
            report.download_url = self.storage_service.create_signed_url(report.storage_path)
        else:
            report.download_url = None

        return report

    def list_reports(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> List[Report]:
        reports = self.repository.list_by_project(project_id, organization_id)
        for r in reports:
            if r.status == ReportStatus.COMPLETED and r.storage_path:
                r.download_url = self.storage_service.create_signed_url(r.storage_path)
            else:
                r.download_url = None
        return reports

    # -------------------------------------------------------------
    # Helper: format values cleanly
    # -------------------------------------------------------------
    @staticmethod
    def _format_val(val: Any) -> str:
        if val is None or val == "null" or val == "None" or val == "":
            return "-"
        if isinstance(val, str):
            trimmed = val.strip()
            if not trimmed or trimmed == "null" or trimmed == "None":
                return "-"
            if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
                try:
                    val = json.loads(trimmed)
                except Exception:
                    return trimmed.replace('\\', '')
            else:
                return trimmed.replace('\\', '')
        if isinstance(val, dict):
            width = val.get("width") or val.get("w")
            height = val.get("height") or val.get("h")
            depth = val.get("depth") or val.get("d")
            opening = val.get("opening")
            if opening:
                return str(opening).replace('\\', '')
            if width or height or depth:
                dims = [str(x).replace('\\', '').strip() for x in [width, height, depth] if x is not None and str(x).strip() != "" and str(x) != "null"]
                if dims:
                    return " × ".join(dims)
            parts = [f"{k}: {str(v).replace('\\', '')}" for k, v in val.items() if v is not None and str(v) != "null" and str(v) != ""]
            return ", ".join(parts) if parts else "-"
        if isinstance(val, list):
            if not val:
                return "-"
            return "; ".join(str(v).replace('\\', '') for v in val if v is not None)
        return str(val).replace('\\', '').strip()

    # -------------------------------------------------------------
    # 1. Deterministic Machine-Readable CSV Export
    # -------------------------------------------------------------
    def generate_csv_data(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> str:
        project = self.db.scalars(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id
            )
        ).first()
        if not project:
            raise ResourceNotFoundError(message="Project not found")

        # Load match groups, line items, and discrepancies
        match_groups = self.db.scalars(
            select(MatchGroup).where(
                MatchGroup.project_id == project_id,
                MatchGroup.organization_id == organization_id
            ).order_by(MatchGroup.created_at.asc())
        ).all()

        discrepancies = self.db.scalars(
            select(Discrepancy).where(
                Discrepancy.project_id == project_id,
                Discrepancy.organization_id == organization_id
            )
        ).all()

        reviews = self.db.scalars(
            select(HumanReview).where(
                HumanReview.project_id == project_id,
                HumanReview.organization_id == organization_id
            )
        ).all()

        # Map discrepancies & reviews by match_group_id
        mg_disc_map: Dict[uuid.UUID, List[Discrepancy]] = {}
        for d in discrepancies:
            mg_disc_map.setdefault(d.match_group_id, []).append(d)

        disc_review_map: Dict[uuid.UUID, HumanReview] = {}
        mg_review_map: Dict[uuid.UUID, HumanReview] = {}
        for r in reviews:
            if r.discrepancy_id:
                disc_review_map[r.discrepancy_id] = r
            if r.match_group_id:
                mg_review_map[r.match_group_id] = r

        output = io.StringIO()
        fieldnames = [
            "project_id",
            "project_name",
            "match_group_id",
            "sku",
            "description",
            "design_quantity",
            "order_quantity",
            "ack_quantity",
            "design_dimensions",
            "order_dimensions",
            "ack_dimensions",
            "design_finish",
            "order_finish",
            "ack_finish",
            "design_door_style",
            "order_door_style",
            "ack_door_style",
            "discrepancy_type",
            "severity",
            "confidence",
            "introduced_at",
            "reason",
            "status",
            "review_status",
            "final_sku",
            "final_quantity",
            "final_dimensions",
            "final_finish",
            "final_door_style",
            "final_modifications",
            "final_price"
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()

        for mg in match_groups:
            d_item = mg.design_item
            o_item = mg.order_item
            a_item = mg.ack_item

            # Representative SKU & Description
            rep_sku = mg.final_sku or (d_item.normalized_sku if d_item else None) or (o_item.normalized_sku if o_item else None) or (a_item.normalized_sku if a_item else "")
            rep_desc = (d_item.description if d_item else None) or (o_item.description if o_item else None) or (a_item.description if a_item else "") or ""

            d_qty = _get_item_qty(d_item)
            o_qty = _get_item_qty(o_item)
            a_qty = _get_item_qty(a_item)

            base_row = {
                "project_id": str(project.id),
                "project_name": project.name or "",
                "match_group_id": str(mg.id),
                "sku": rep_sku or "",
                "description": rep_desc or "",
                "design_quantity": str(d_qty) if d_qty is not None else "",
                "order_quantity": str(o_qty) if o_qty is not None else "",
                "ack_quantity": str(a_qty) if a_qty is not None else "",
                "design_dimensions": self._format_val(d_item.dimensions) if d_item else "",
                "order_dimensions": self._format_val(o_item.dimensions) if o_item else "",
                "ack_dimensions": self._format_val(a_item.dimensions) if a_item else "",
                "design_finish": d_item.finish or "" if d_item else "",
                "order_finish": o_item.finish or "" if o_item else "",
                "ack_finish": a_item.finish or "" if a_item else "",
                "design_door_style": d_item.door_style or "" if d_item else "",
                "order_door_style": o_item.door_style or "" if o_item else "",
                "ack_door_style": a_item.door_style or "" if a_item else "",
                "status": mg.status.value if hasattr(mg.status, 'value') else str(mg.status),
                "final_sku": mg.final_sku or "",
                "final_quantity": str(mg.final_quantity) if mg.final_quantity is not None else "",
                "final_dimensions": self._format_val(mg.final_dimensions),
                "final_finish": mg.final_finish or "",
                "final_door_style": mg.final_door_style or "",
                "final_modifications": self._format_val(mg.final_modifications),
                "final_price": mg.final_price or "",
            }

            m_discs = mg_disc_map.get(mg.id, [])
            if not m_discs:
                # No discrepancies for this match group
                row = dict(base_row)
                row["discrepancy_type"] = ""
                row["severity"] = ""
                row["confidence"] = ""
                row["introduced_at"] = ""
                row["reason"] = ""
                row["review_status"] = ""
                writer.writerow(row)
            else:
                for d in m_discs:
                    row = dict(base_row)
                    row["discrepancy_type"] = d.field or ""
                    row["severity"] = d.severity.value if hasattr(d.severity, 'value') else str(d.severity)
                    row["confidence"] = d.confidence or ""
                    row["introduced_at"] = d.introduced_at.value if hasattr(d.introduced_at, 'value') else (str(d.introduced_at) if d.introduced_at else "")
                    row["reason"] = d.explanation or ""

                    # Review status
                    rev = disc_review_map.get(d.id) or mg_review_map.get(mg.id)
                    row["review_status"] = (rev.action.value if hasattr(rev.action, 'value') else str(rev.action)) if rev else d.status
                    writer.writerow(row)

        return output.getvalue()

    # -------------------------------------------------------------
    # 2. Production-Safe PDF Report Generation
    # -------------------------------------------------------------
    def generate_pdf_bytes(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> bytes:
        project = self.db.scalars(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id
            )
        ).first()
        if not project:
            raise ResourceNotFoundError(message="Project not found")

        # Load all related records
        documents = self.db.scalars(
            select(Document).where(
                Document.project_id == project_id,
                Document.organization_id == organization_id
            ).order_by(Document.created_at.asc())
        ).all()

        match_groups = self.db.scalars(
            select(MatchGroup).where(
                MatchGroup.project_id == project_id,
                MatchGroup.organization_id == organization_id
            ).order_by(MatchGroup.created_at.asc())
        ).all()

        discrepancies = self.db.scalars(
            select(Discrepancy).where(
                Discrepancy.project_id == project_id,
                Discrepancy.organization_id == organization_id
            ).order_by(Discrepancy.created_at.asc())
        ).all()

        reviews = self.db.scalars(
            select(HumanReview).where(
                HumanReview.project_id == project_id,
                HumanReview.organization_id == organization_id
            ).order_by(HumanReview.created_at.desc())
        ).all()

        audit_logs = self.db.scalars(
            select(AuditLog).where(
                AuditLog.project_id == project_id,
                AuditLog.organization_id == organization_id
            ).order_by(AuditLog.created_at.desc())
        ).all()

        # Build metrics
        total_mg = len(match_groups)
        matched_cnt = sum(1 for mg in match_groups if mg.status == MatchGroupStatus.MATCHED)
        changed_cnt = sum(1 for mg in match_groups if mg.status == MatchGroupStatus.CHANGED)
        missing_cnt = sum(1 for mg in match_groups if mg.status == MatchGroupStatus.MISSING)
        extra_cnt = sum(1 for mg in match_groups if mg.status == MatchGroupStatus.EXTRA)
        uncertain_cnt = sum(1 for mg in match_groups if mg.status == MatchGroupStatus.UNCERTAIN)

        critical_disc = sum(1 for d in discrepancies if (d.severity.value if hasattr(d.severity, 'value') else str(d.severity)) in ["Critical", "CRITICAL"])
        warning_disc = sum(1 for d in discrepancies if (d.severity.value if hasattr(d.severity, 'value') else str(d.severity)) in ["Warning", "WARNING"])
        info_disc = sum(1 for d in discrepancies if (d.severity.value if hasattr(d.severity, 'value') else str(d.severity)) in ["Info", "INFO"])

        # Setup ReportLab Doc
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=46,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()
        
        # Color palette
        PRIMARY = colors.HexColor("#0F172A")    # Slate 900
        SECONDARY = colors.HexColor("#1E293B")  # Slate 800
        ACCENT_BLUE = colors.HexColor("#2563EB")# Blue 600
        TEXT_DARK = colors.HexColor("#334155")  # Slate 700
        MUTED_TEXT = colors.HexColor("#64748B") # Slate 500
        BG_LIGHT = colors.HexColor("#F8FAFC")   # Slate 50
        BORDER_COLOR = colors.HexColor("#E2E8F0")# Slate 200
        RED_COLOR = colors.HexColor("#DC2626")  # Red 600
        AMBER_COLOR = colors.HexColor("#D97706")# Amber 600
        GREEN_COLOR = colors.HexColor("#16A34A")# Green 600

        # Custom Typography Styles
        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=PRIMARY
        )
        subtitle_style = ParagraphStyle(
            'DocSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=MUTED_TEXT
        )
        h2_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            textColor=PRIMARY,
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=8.5,
            leading=11,
            textColor=TEXT_DARK
        )
        body_bold = ParagraphStyle(
            'BodyBold',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8.5,
            leading=11,
            textColor=PRIMARY
        )
        th_style = ParagraphStyle(
            'TableHeader',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white
        )
        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7.5,
            leading=10,
            textColor=TEXT_DARK
        )
        badge_crit = ParagraphStyle(
            'BadgeCrit',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            textColor=RED_COLOR
        )
        badge_warn = ParagraphStyle(
            'BadgeWarn',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            textColor=AMBER_COLOR
        )
        badge_info = ParagraphStyle(
            'BadgeInfo',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            textColor=ACCENT_BLUE
        )
        reason_style = ParagraphStyle(
            'ReasonText',
            parent=styles['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=7.5,
            leading=10,
            textColor=MUTED_TEXT
        )
        badge_succ = ParagraphStyle(
            'BadgeSucc',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=7.5,
            leading=9,
            textColor=GREEN_COLOR
        )

        elements = []

        # =========================================================
        # 1. HEADER & BRANDING
        # =========================================================
        brand_data = [
            [
                Paragraph("<b>CROSSCHECK</b><font color='#2563EB'>PRO</font>", title_style),
                Paragraph(f"<b>PROJECT AUDIT & VERIFICATION REPORT</b><br/><font color='#64748B'>Report ID: {uuid.uuid4().hex[:12].upper()}</font>", ParagraphStyle('RAlign', parent=subtitle_style, alignment=2))
            ]
        ]
        brand_table = Table(brand_data, colWidths=[270, 270])
        brand_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        elements.append(brand_table)
        elements.append(Spacer(1, 4))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT_BLUE, spaceBefore=4, spaceAfter=8))

        # =========================================================
        # 2. PROJECT SUMMARY & DOCUMENT INFO
        # =========================================================
        status_str = project.status.value if hasattr(project.status, 'value') else str(project.status)
        finalized_badge = "YES (FINALIZED)" if status_str == "FINALIZED" else f"NO ({status_str})"

        meta_left = [
            [Paragraph("Project Name:", body_bold), Paragraph(project.name or "Unnamed", body_style)],
            [Paragraph("Project ID:", body_bold), Paragraph(str(project.id), body_style)],
            [Paragraph("Customer:", body_bold), Paragraph(project.customer_name or "N/A", body_style)],
            [Paragraph("Dealer:", body_bold), Paragraph(project.dealer_name or "N/A", body_style)],
            [Paragraph("Created Date:", body_bold), Paragraph(project.created_at.strftime("%Y-%m-%d %H:%M") if project.created_at else "N/A", body_style)],
            [Paragraph("Finalized Status:", body_bold), Paragraph(f"<b>{finalized_badge}</b>", badge_succ if status_str == "FINALIZED" else body_style)],
        ]
        meta_left_table = Table(meta_left, colWidths=[90, 170])
        meta_left_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))

        doc_by_type = { (d.document_type.name if hasattr(d.document_type, 'name') else str(d.document_type)): d for d in documents }
        design_d = doc_by_type.get("DESIGN")
        order_d = doc_by_type.get("ORDER")
        ack_d = doc_by_type.get("ACKNOWLEDGEMENT")

        meta_right = [
            [Paragraph("<b>Document Source</b>", body_bold), Paragraph("<b>File / Status</b>", body_bold)],
            [
                Paragraph("1. Design Document:", body_bold),
                Paragraph(f"{design_d.original_filename} ({design_d.status})" if design_d else "<font color='#DC2626'>Missing</font>", body_style)
            ],
            [
                Paragraph("2. Order Document:", body_bold),
                Paragraph(f"{order_d.original_filename} ({order_d.status})" if order_d else "<font color='#DC2626'>Missing</font>", body_style)
            ],
            [
                Paragraph("3. Acknowledgement:", body_bold),
                Paragraph(f"{ack_d.original_filename} ({ack_d.status})" if ack_d else "<font color='#DC2626'>Missing</font>", body_style)
            ],
            [
                Paragraph("Total Documents:", body_bold),
                Paragraph(f"{len(documents)} uploaded", body_style)
            ],
        ]
        meta_right_table = Table(meta_right, colWidths=[110, 160])
        meta_right_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))

        project_info_container = Table([
            [meta_left_table, meta_right_table]
        ], colWidths=[265, 275])
        project_info_container.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
            ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(project_info_container)
        elements.append(Spacer(1, 8))

        # =========================================================
        # 3. THREE-WAY CROSS-CHECK SUMMARY METRICS
        # =========================================================
        elements.append(Paragraph("Cross-Check Summary", h2_style))
        summary_cards = [
            [
                Paragraph("<font size=7 color='#64748B'>MATCHED</font><br/><font size=12><b>" + str(matched_cnt) + "</b></font>", ParagraphStyle('C1', parent=body_style, alignment=1)),
                Paragraph("<font size=7 color='#64748B'>CHANGED</font><br/><font size=12><b>" + str(changed_cnt) + "</b></font>", ParagraphStyle('C2', parent=body_style, alignment=1)),
                Paragraph("<font size=7 color='#64748B'>MISSING</font><br/><font size=12><b>" + str(missing_cnt) + "</b></font>", ParagraphStyle('C3', parent=body_style, alignment=1)),
                Paragraph("<font size=7 color='#64748B'>EXTRA</font><br/><font size=12><b>" + str(extra_cnt) + "</b></font>", ParagraphStyle('C4', parent=body_style, alignment=1)),
                Paragraph("<font size=7 color='#64748B'>UNCERTAIN</font><br/><font size=12><b>" + str(uncertain_cnt) + "</b></font>", ParagraphStyle('C5', parent=body_style, alignment=1)),
                Paragraph("<font size=7 color='#DC2626'>CRITICAL</font><br/><font size=12 color='#DC2626'><b>" + str(critical_disc) + "</b></font>", ParagraphStyle('C6', parent=body_style, alignment=1)),
                Paragraph("<font size=7 color='#D97706'>WARNING</font><br/><font size=12 color='#D97706'><b>" + str(warning_disc) + "</b></font>", ParagraphStyle('C7', parent=body_style, alignment=1)),
                Paragraph("<font size=7 color='#2563EB'>INFO</font><br/><font size=12 color='#2563EB'><b>" + str(info_disc) + "</b></font>", ParagraphStyle('C8', parent=body_style, alignment=1)),
            ]
        ]
        summary_table = Table(summary_cards, colWidths=[67.5]*8)
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
            ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
            ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 10))

        # =========================================================
        # 4. DETAILED DISCREPANCY TABLE
        # =========================================================
        elements.append(Paragraph(f"Detailed Discrepancies ({len(discrepancies)} Detected)", h2_style))
        if not discrepancies:
            elements.append(Paragraph("<i>No discrepancies detected. All three documents are perfectly aligned.</i>", body_style))
        else:
            disc_headers = [
                Paragraph("SKU", th_style),
                Paragraph("Field / Type", th_style),
                Paragraph("Design", th_style),
                Paragraph("Order", th_style),
                Paragraph("Ack", th_style),
                Paragraph("Severity", th_style),
                Paragraph("Introduced At", th_style),
                Paragraph("Status", th_style)
            ]
            disc_rows = [disc_headers]
            reason_row_indices: List[int] = []

            mg_map = {mg.id: mg for mg in match_groups}
            for d in discrepancies:
                mg = mg_map.get(d.match_group_id)
                sku_text = mg.final_sku or (mg.design_item.normalized_sku if mg and mg.design_item else "") or (mg.order_item.normalized_sku if mg and mg.order_item else "") or (mg.ack_item.normalized_sku if mg and mg.ack_item else "N/A")
                
                # Extract values from source_values & comparison_values
                src_vals = d.source_values
                if isinstance(src_vals, str):
                    try:
                        src_vals = json.loads(src_vals)
                    except Exception:
                        src_vals = {}
                elif not isinstance(src_vals, dict):
                    src_vals = {}

                comp_vals = d.comparison_values
                if isinstance(comp_vals, str):
                    try:
                        comp_vals = json.loads(comp_vals)
                    except Exception:
                        comp_vals = {}
                elif not isinstance(comp_vals, dict):
                    comp_vals = {}
                
                d_val = src_vals.get("design") or comp_vals.get("design") or (getattr(mg.design_item, d.field, None) if mg and mg.design_item else "")
                o_val = src_vals.get("order") or comp_vals.get("order") or (getattr(mg.order_item, d.field, None) if mg and mg.order_item else "")
                a_val = src_vals.get("acknowledgement") or comp_vals.get("acknowledgement") or (getattr(mg.ack_item, d.field, None) if mg and mg.ack_item else "")

                sev_str = d.severity.value if hasattr(d.severity, 'value') else str(d.severity)
                if sev_str in ["Critical", "CRITICAL"]:
                    sev_p = Paragraph(f"<b>{sev_str}</b>", badge_crit)
                elif sev_str in ["Warning", "WARNING"]:
                    sev_p = Paragraph(f"<b>{sev_str}</b>", badge_warn)
                else:
                    sev_p = Paragraph(f"{sev_str}", badge_info)

                intro_str = d.introduced_at.value if hasattr(d.introduced_at, 'value') else (str(d.introduced_at) if d.introduced_at else "-")
                status_p = Paragraph(d.status, badge_succ if d.status in ("ACCEPTED", "ACKNOWLEDGED", "RESOLVED") else body_style)

                disc_rows.append([
                    Paragraph(f"<b>{sku_text}</b>", cell_style),
                    Paragraph(d.field or "-", cell_style),
                    Paragraph(self._format_val(d_val) or "-", cell_style),
                    Paragraph(self._format_val(o_val) or "-", cell_style),
                    Paragraph(self._format_val(a_val) or "-", cell_style),
                    sev_p,
                    Paragraph(intro_str, cell_style),
                    status_p
                ])

                # Reason row: full-width explanation of why this discrepancy was flagged
                reason_text = d.explanation or "No explanation recorded for this discrepancy."
                reason_row_idx = len(disc_rows)
                disc_rows.append([
                    Paragraph(f"<b>Reason:</b> {reason_text}", reason_style),
                    "", "", "", "", "", "", ""
                ])
                reason_row_indices.append(reason_row_idx)

            # Total printable width: 540 pt
            disc_table = Table(disc_rows, colWidths=[70, 75, 65, 65, 65, 60, 70, 70], repeatRows=1)
            table_style_cmds = [
                ('BACKGROUND', (0,0), (-1,0), PRIMARY),
                ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
                ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ]
            for idx in reason_row_indices:
                table_style_cmds.append(('SPAN', (0, idx), (-1, idx)))
                table_style_cmds.append(('BACKGROUND', (0, idx), (-1, idx), BG_LIGHT))
            disc_table.setStyle(TableStyle(table_style_cmds))
            elements.append(disc_table)

        elements.append(Spacer(1, 10))

        # =========================================================
        # 5. FINAL RESOLVED STATE TABLE
        # =========================================================
        elements.append(Paragraph("Final Resolved State", h2_style))
        final_headers = [
            Paragraph("Final SKU", th_style),
            Paragraph("Qty", th_style),
            Paragraph("Dimensions", th_style),
            Paragraph("Finish", th_style),
            Paragraph("Door Style", th_style),
            Paragraph("Modifications", th_style),
            Paragraph("Price", th_style),
            Paragraph("Status", th_style)
        ]
        final_rows = [final_headers]
        for mg in match_groups:
            sku_p = Paragraph(f"<b>{mg.final_sku or 'N/A'}</b>", cell_style)
            qty_p = Paragraph(str(mg.final_quantity) if mg.final_quantity is not None else "-", cell_style)
            dim_p = Paragraph(self._format_val(mg.final_dimensions) or "-", cell_style)
            fin_p = Paragraph(mg.final_finish or "-", cell_style)
            door_p = Paragraph(mg.final_door_style or "-", cell_style)
            mods_p = Paragraph(self._format_val(mg.final_modifications) or "-", cell_style)
            price_p = Paragraph(mg.final_price or "-", cell_style)
            st_p = Paragraph(mg.final_status or (mg.status.value if hasattr(mg.status, 'value') else str(mg.status)), cell_style)

            final_rows.append([sku_p, qty_p, dim_p, fin_p, door_p, mods_p, price_p, st_p])

        final_table = Table(final_rows, colWidths=[75, 30, 85, 70, 70, 100, 50, 60], repeatRows=1)
        final_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), SECONDARY),
            ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
            ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
        ]))
        elements.append(final_table)
        elements.append(Spacer(1, 10))

        # =========================================================
        # 6. HUMAN REVIEW & AUDIT LOG INFORMATION
        # =========================================================
        if reviews:
            elements.append(Paragraph(f"Human Review History ({len(reviews)} Actions)", h2_style))
            rev_headers = [
                Paragraph("Action", th_style),
                Paragraph("Reviewer", th_style),
                Paragraph("Timestamp", th_style),
                Paragraph("Reason / Notes", th_style)
            ]
            rev_rows = [rev_headers]
            for r in reviews:
                act_str = r.action.value if hasattr(r.action, 'value') else str(r.action)
                rev_user = r.reviewer.email if r.reviewer else (str(r.reviewer_id) if r.reviewer_id else "System")
                dt_str = r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "-"
                notes_str = r.reason or "-"
                rev_rows.append([
                    Paragraph(f"<b>{act_str}</b>", cell_style),
                    Paragraph(rev_user, cell_style),
                    Paragraph(dt_str, cell_style),
                    Paragraph(notes_str, cell_style)
                ])

            rev_table = Table(rev_rows, colWidths=[120, 120, 100, 200], repeatRows=1)
            rev_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), PRIMARY),
                ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
                ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
            ]))
            elements.append(rev_table)
            elements.append(Spacer(1, 10))

        if audit_logs:
            elements.append(Paragraph(f"Audit Trail (Recent Events)", h2_style))
            audit_headers = [
                Paragraph("Action", th_style),
                Paragraph("Actor", th_style),
                Paragraph("Resource", th_style),
                Paragraph("Timestamp", th_style)
            ]
            audit_rows = [audit_headers]
            for a in audit_logs[:15]: # Show up to 15 most recent
                actor_str = a.actor.email if a.actor else (str(a.actor_id) if a.actor_id else "System")
                dt_str = a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "-"
                res_str = f"{a.resource_type}:{str(a.resource_id)[:8]}"
                audit_rows.append([
                    Paragraph(a.action, cell_style),
                    Paragraph(actor_str, cell_style),
                    Paragraph(res_str, cell_style),
                    Paragraph(dt_str, cell_style)
                ])

            audit_table = Table(audit_rows, colWidths=[160, 140, 120, 120], repeatRows=1)
            audit_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), SECONDARY),
                ('BOX', (0,0), (-1,-1), 1, BORDER_COLOR),
                ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, BG_LIGHT])
            ]))
            elements.append(audit_table)

        # Build document with NumberedCanvas
        doc.build(elements, canvasmaker=NumberedCanvas)
        return buffer.getvalue()

    # -------------------------------------------------------------
    # 3. Asynchronous Execution by Celery Worker
    # -------------------------------------------------------------
    def process_report_job(self, report_id: uuid.UUID) -> Report:
        report = self.repository.get_by_id(report_id)
        if not report:
            raise ResourceNotFoundError(message="Report not found")

        # Set status to GENERATING
        self.repository.update_status(report, ReportStatus.GENERATING)

        try:
            if report.format == ReportFormat.CSV:
                csv_data = self.generate_csv_data(report.project_id, report.organization_id)
                csv_bytes = csv_data.encode("utf-8")
                storage_path = f"reports/{report.organization_id}/{report.project_id}/{report.id}.csv"
                self.storage_service.upload_file(storage_path, csv_bytes, "text/csv")
            else: # PDF
                pdf_bytes = self.generate_pdf_bytes(report.project_id, report.organization_id)
                storage_path = f"reports/{report.organization_id}/{report.project_id}/{report.id}.pdf"
                self.storage_service.upload_file(storage_path, pdf_bytes, "application/pdf")

            completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.repository.update_status(
                report=report,
                status=ReportStatus.COMPLETED,
                storage_path=storage_path,
                completed_at=completed_at
            )
            return report
        except Exception as e:
            self.repository.update_status(
                report=report,
                status=ReportStatus.FAILED,
                error={"message": str(e), "type": type(e).__name__}
            )
            raise e
