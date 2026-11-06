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
            o_item = mg.cabinet_list_item
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
    # 2. Production-Safe PDF Report Generation  (customer-friendly layout)
    # -------------------------------------------------------------
    def generate_pdf_bytes(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> bytes:  # noqa: C901
        project = self.db.scalars(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id
            )
        ).first()
        if not project:
            raise ResourceNotFoundError(message="Project not found")

        # --- load data ---
        documents = self.db.scalars(select(Document).where(Document.project_id == project_id, Document.organization_id == organization_id).order_by(Document.created_at.asc())).all()
        match_groups = self.db.scalars(select(MatchGroup).where(MatchGroup.project_id == project_id, MatchGroup.organization_id == organization_id).order_by(MatchGroup.created_at.asc())).all()
        discrepancies = self.db.scalars(select(Discrepancy).where(Discrepancy.project_id == project_id, Discrepancy.organization_id == organization_id).order_by(Discrepancy.created_at.asc())).all()

        mg_disc_map: Dict[uuid.UUID, List[Discrepancy]] = {}
        for d in discrepancies:
            mg_disc_map.setdefault(d.match_group_id, []).append(d)

        # --- helpers ---
        FIELD_LABELS = {
            "item_presence": "Item Presence", "quantity": "Quantity",
            "finish": "Color / Finish", "door_style": "Door Style",
            "dimensions": "Size / Dimensions", "species": "Wood Species",
            "construction": "Box Construction", "drawer_box": "Drawer Box",
            "sku": "Item Code", "description": "Description",
        }
        def _fl(f): return FIELD_LABELS.get(f, (f or "").replace("_", " ").title())
        def _sku(mg):
            d, o, a = mg.design_item, mg.cabinet_list_item, mg.ack_item
            return mg.final_sku or (d.normalized_sku if d else None) or (o.normalized_sku if o else None) or (a.normalized_sku if a else "N/A") or "N/A"
        def _desc(mg):
            d, o, a = mg.design_item, mg.cabinet_list_item, mg.ack_item
            return (d.description if d and d.description else None) or (o.description if o and o.description else None) or (a.description if a and a.description else None) or "-"
        def _sv(d_obj):
            sv = d_obj.source_values
            if isinstance(sv, str):
                try: sv = json.loads(sv)
                except Exception: sv = {}
            return sv if isinstance(sv, dict) else {}

        def _mg_status(mg): return mg.status.value if hasattr(mg.status, "value") else str(mg.status)

        active_mgs   = [mg for mg in match_groups if _mg_status(mg) != "OUT_OF_SCOPE"]
        matched_mgs  = [mg for mg in active_mgs if _mg_status(mg) == "MATCHED"]
        changed_mgs  = [mg for mg in active_mgs if _mg_status(mg) == "CHANGED"]
        missing_mgs  = [mg for mg in active_mgs if _mg_status(mg) == "MISSING"]
        extra_mgs    = [mg for mg in active_mgs if _mg_status(mg) == "EXTRA"]
        uncertain_mgs= [mg for mg in active_mgs if _mg_status(mg) == "UNCERTAIN"]

        total = len(active_mgs) or 1
        matched_pct = len(matched_mgs) / total * 100
        has_critical = any((d.severity.value if hasattr(d.severity, "value") else str(d.severity)).upper() == "CRITICAL" for d in discrepancies)

        doc_by_type = {(d.document_type.name if hasattr(d.document_type, "name") else str(d.document_type)): d for d in documents}
        design_d = doc_by_type.get("DESIGN")
        order_d = doc_by_type.get("ORDER") or doc_by_type.get("CABINET_LIST")
        ack_d = doc_by_type.get("ACKNOWLEDGEMENT")

        # --- PDF setup ---
        buffer = io.BytesIO()
        pdf_doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=46, bottomMargin=54)
        styles = getSampleStyleSheet()

        GREEN      = colors.HexColor("#16A34A"); ORANGE    = colors.HexColor("#EA580C")
        RED        = colors.HexColor("#DC2626"); BLUE_A    = colors.HexColor("#2563EB")
        AMBER      = colors.HexColor("#D97706"); GREY      = colors.HexColor("#64748B")
        SLATE_900  = colors.HexColor("#0F172A"); SLATE_700 = colors.HexColor("#334155")
        SLATE_200  = colors.HexColor("#E2E8F0"); SLATE_50  = colors.HexColor("#F8FAFC")
        GREEN_BG   = colors.HexColor("#F0FDF4"); ORANGE_BG = colors.HexColor("#FFF7ED")
        RED_BG     = colors.HexColor("#FEF2F2"); BLUE_BG   = colors.HexColor("#EFF6FF")
        AMBER_BG   = colors.HexColor("#FFFBEB"); WHITE     = colors.white
        NAVY       = colors.HexColor("#1E3A5F"); ROW_ALT   = colors.HexColor("#F3F6F9")

        def _ps(name, **kw):
            return ParagraphStyle(name, parent=kw.pop("parent", styles["Normal"]), **kw)
        body      = _ps("body",   fontName="Helvetica",       fontSize=8.5, leading=12, textColor=SLATE_700)
        small     = _ps("small",  fontName="Helvetica",       fontSize=7.5, leading=10, textColor=SLATE_700)
        small_b   = _ps("smallb", fontName="Helvetica-Bold",  fontSize=7.5, leading=10, textColor=SLATE_900)
        italic_s  = _ps("italic", fontName="Helvetica-Oblique", fontSize=8.5, leading=11, textColor=GREY)
        th_s      = _ps("th",     fontName="Helvetica-Bold",  fontSize=8,   leading=10, textColor=WHITE)
        kpi_num_s = _ps("kpin",   fontName="Helvetica-Bold",  fontSize=22,  leading=26, alignment=1)
        kpi_lbl_s = _ps("kpil",   fontName="Helvetica",       fontSize=7,   leading=9,  alignment=1, textColor=GREY)
        title_lg  = _ps("titlel", fontName="Helvetica-Bold",  fontSize=22,  leading=26, textColor=NAVY)
        title_sm  = _ps("titles", fontName="Helvetica-Bold",  fontSize=14,  leading=18, textColor=SLATE_900)
        subtitle  = _ps("sub",    fontName="Helvetica",       fontSize=9,   leading=12, textColor=GREY)

        def sec_hdr(text, col):
            # Left accent bar + dark navy text — cleaner than colored text
            cell = Table([[Paragraph(f"<b>{text}</b>", _ps(f"sh{text[:6].replace(' ','')}", fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=NAVY, spaceBefore=0, spaceAfter=0))]], colWidths=[530])
            cell.setStyle(TableStyle([
                ("LEFTPADDING",(0,0),(-1,-1),10), ("RIGHTPADDING",(0,0),(-1,-1),4),
                ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
                ("LINEBEFORE",(0,0),(0,-1),4,col),
                ("BACKGROUND",(0,0),(-1,-1),SLATE_50),
            ]))
            return [Spacer(1,10), cell, Spacer(1,6)]

        def tbl_style(accent_col=None, row_bgs=None, border=None):
            # Professional: dark navy header, subtle alternating rows — accent_col/row_bgs kept for compat
            bc = border or colors.HexColor("#DCE6F0")
            return TableStyle([
                ("BACKGROUND", (0,0), (-1,0), NAVY),
                ("BOX", (0,0), (-1,-1), 0.75, bc),
                ("INNERGRID", (0,0), (-1,-1), 0.4, bc),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
                ("ROWBACKGROUNDS", (0,1), (-1,-1), [WHITE, ROW_ALT]),
            ])

        els = []

        # -- 1. HEADER --
        hdr = Table([
            [Paragraph("<b>CROSSCHECK<font color='#2563EB'>PRO</font></b>", title_lg), Paragraph(f"<b>{project.name or 'Unnamed Project'}</b>", title_sm)],
            [Paragraph("Cabinet Order Verification Report", subtitle), Paragraph(f"Customer: {project.customer_name or 'N/A'}  |  Dealer: {project.dealer_name or 'N/A'}", subtitle)],
            ["", Paragraph(f"Date: {datetime.datetime.now(datetime.timezone.utc).strftime('%B %d, %Y')}", subtitle)],
        ], colWidths=[270, 270])
        hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),2),("BOTTOMPADDING",(0,0),(-1,-1),2)]))
        els.append(hdr)
        els.append(HRFlowable(width="100%", thickness=2, color=BLUE_A, spaceBefore=6, spaceAfter=10))

        # -- 2. STATUS BANNER --
        if matched_pct >= 90 and not has_critical:
            b_col, b_bg, b_txt = GREEN, GREEN_BG, "\u2713  LOOKING GOOD \u2014 Minor items need your attention."
        elif matched_pct >= 70:
            b_col, b_bg, b_txt = ORANGE, ORANGE_BG, "\u25ce  REVIEW REQUIRED \u2014 Several items need to be verified."
        else:
            b_col, b_bg, b_txt = RED, RED_BG, "\u26a0  ACTION REQUIRED \u2014 Important differences found that must be resolved."
        banner = Table([[Paragraph(b_txt, _ps("ban", fontName="Helvetica-Bold", fontSize=10, leading=13, textColor=b_col))]], colWidths=[540])
        banner.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),b_bg),("LINEBEFORE",(0,0),(0,-1),4,b_col),("LINEBELOW",(0,-1),(-1,-1),0.5,colors.HexColor("#DCE6F0")),("LINEABOVE",(0,0),(-1,0),0.5,colors.HexColor("#DCE6F0")),("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9),("LEFTPADDING",(0,0),(-1,-1),14)]))
        els.append(banner); els.append(Spacer(1, 10))

        # -- 3. EXECUTIVE SUMMARY --
        els += sec_hdr("Executive Summary", BLUE_A)
        kpi_specs = [
            (str(len(active_mgs)),  "Total Items\nChecked",    BLUE_BG,   BLUE_A),
            (str(len(matched_mgs)), "Items That\nMatch",       GREEN_BG,  GREEN),
            (str(len(changed_mgs)), "Items With\nDifferences", ORANGE_BG, ORANGE),
            (str(len(missing_mgs)+len(extra_mgs)), "Missing /\nExtra", RED_BG, RED),
            (str(len(uncertain_mgs)),"Needs\nConfirmation",   SLATE_50,  GREY),
        ]
        kpi_cells = []
        for num, lbl, bg, col in kpi_specs:
            inner = Table([[Paragraph(f"<font color='{col.hexval()}'><b>{num}</b></font>", kpi_num_s)],[Paragraph(lbl, kpi_lbl_s)]], colWidths=[100])
            inner.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
            wrap = Table([[inner]], colWidths=[106])
            wrap.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,-1),WHITE),
                ("BOX",(0,0),(-1,-1),0.75,colors.HexColor("#DCE6F0")),
                ("LINEABOVE",(0,0),(-1,0),3,col),  # colored top accent bar
                ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
                ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
            ]))
            kpi_cells.append(wrap)
        kpi_tbl = Table([kpi_cells], colWidths=[108]*5)
        kpi_tbl.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),1),("RIGHTPADDING",(0,0),(-1,-1),1)]))
        els.append(kpi_tbl); els.append(Spacer(1, 12))

        # -- 4. ITEMS THAT MATCH --
        els += sec_hdr("Items That Match", GREEN)
        els.append(Paragraph("The following items appear correctly across all three documents.", body)); els.append(Spacer(1,4))
        if matched_mgs:
            rows = [[Paragraph(h, th_s) for h in ["Item Code","Description","Qty (Design)","Qty (Order)","Qty (Ack)","Result"]]]
            for mg in matched_mgs:
                d, o, a = mg.design_item, mg.cabinet_list_item, mg.ack_item
                rows.append([Paragraph(f"<b>{_sku(mg)}</b>", small_b), Paragraph(_desc(mg)[:60], small),
                              Paragraph(str(_get_item_qty(d)) if _get_item_qty(d) is not None else "-", small),
                              Paragraph(str(_get_item_qty(o)) if _get_item_qty(o) is not None else "-", small),
                              Paragraph(str(_get_item_qty(a)) if _get_item_qty(a) is not None else "-", small),
                              Paragraph("<font color='#16A34A'><b>\u2713 Match</b></font>", small_b)])
            t = Table(rows, colWidths=[80,180,60,60,60,100], repeatRows=1); t.setStyle(tbl_style(GREEN,[WHITE,GREEN_BG])); els.append(t)
        else:
            els.append(Paragraph("<i>No exact matches found.</i>", italic_s))
        els.append(Spacer(1, 10))

        # -- 5. ITEMS THAT NEED ATTENTION (CHANGED) --
        els += sec_hdr("Items That Need Attention", ORANGE)
        els.append(Paragraph("These items were found in all documents but have specification differences.", body)); els.append(Spacer(1,4))
        if changed_mgs:
            rows = [[Paragraph(h, th_s) for h in ["Item Code","What Changed","In Design Drawing","In Purchase Order","In Mfr. Confirmation","Severity"]]]
            for mg in changed_mgs:
                discs = mg_disc_map.get(mg.id, [])
                if discs:
                    for d in discs:
                        sv = _sv(d)
                        sev = (d.severity.value if hasattr(d.severity,"value") else str(d.severity)).upper()
                        sc = RED if sev=="CRITICAL" else (ORANGE if sev=="WARNING" else GREY)
                        sl = {"CRITICAL":"\u26a0 Action Required","WARNING":"\u25ce Needs Review"}.get(sev,"\u2139 For Your Info")
                        rows.append([Paragraph(f"<b>{_sku(mg)}</b>", small_b), Paragraph(_fl(d.field), small),
                                     Paragraph(self._format_val(sv.get("design") or "-"), small),
                                     Paragraph(self._format_val(sv.get("order") or "-"), small),
                                     Paragraph(self._format_val(sv.get("acknowledgement") or "-"), small),
                                     Paragraph(f"<font color='{sc.hexval()}'><b>{sl}</b></font>", small)])
                else:
                    rows.append([Paragraph(f"<b>{_sku(mg)}</b>", small_b), Paragraph("See Details", small),
                                 Paragraph("-",small),Paragraph("-",small),Paragraph("-",small),Paragraph("\u25ce Needs Review",small)])
            t = Table(rows, colWidths=[75,80,90,90,90,115], repeatRows=1); t.setStyle(tbl_style(ORANGE,[WHITE,ORANGE_BG])); els.append(t)
        else:
            els.append(Paragraph("<i>No specification differences found.</i>", italic_s))
        els.append(Spacer(1, 10))

        # -- 6. MISSING ITEMS --
        els += sec_hdr("Missing Items", RED)
        els.append(Paragraph("These items appear in the Design Drawing but could not be found in the Purchase Order or Manufacturer Confirmation.", body)); els.append(Spacer(1,4))
        if missing_mgs:
            rows = [[Paragraph(h, th_s) for h in ["Item Code","Description","Qty in Design","Found in PO","Found in Ack","Action Needed"]]]
            for mg in missing_mgs:
                d, o, a = mg.design_item, mg.cabinet_list_item, mg.ack_item
                rows.append([Paragraph(f"<b>{_sku(mg)}</b>", small_b), Paragraph(_desc(mg)[:50], small),
                             Paragraph(str(_get_item_qty(d)) if _get_item_qty(d) is not None else "-", small),
                             Paragraph("-" if o else "<font color='#DC2626'>No</font>", small),
                             Paragraph("-" if a else "<font color='#DC2626'>No</font>", small),
                             Paragraph("Confirm with dealer \u2014 item is in design but not ordered.", small)])
            t = Table(rows, colWidths=[75,120,60,60,60,165], repeatRows=1); t.setStyle(tbl_style(RED,[WHITE,RED_BG])); els.append(t)
        else:
            els.append(Paragraph("<i><font color='#16A34A'>No missing items \u2014 all design items accounted for.</font></i>", italic_s))
        els.append(Spacer(1, 10))

        # -- 7. EXTRA ITEMS --
        els += sec_hdr("Extra Items", AMBER)
        els.append(Paragraph("These items appear in the Purchase Order but were not found in the Design Drawing.", body)); els.append(Spacer(1,4))
        if extra_mgs:
            rows = [[Paragraph(h, th_s) for h in ["Item Code","Description","Qty Ordered","Found in Design","Note"]]]
            for mg in extra_mgs:
                d, o, a = mg.design_item, mg.cabinet_list_item, mg.ack_item
                rows.append([Paragraph(f"<b>{_sku(mg)}</b>", small_b), Paragraph(_desc(mg)[:50], small),
                             Paragraph(str(_get_item_qty(o)) if _get_item_qty(o) is not None else "-", small),
                             Paragraph("-" if d else "<font color='#D97706'>Not in Design</font>", small),
                             Paragraph("Verify this is an intentional addition or an appliance/accessory not shown in the design.", small)])
            t = Table(rows, colWidths=[75,120,60,80,205], repeatRows=1); t.setStyle(tbl_style(AMBER,[WHITE,AMBER_BG])); els.append(t)
        else:
            els.append(Paragraph("<i>No extra items found.</i>", italic_s))
        els.append(Spacer(1, 10))

        # -- 8. NEEDS CONFIRMATION (UNCERTAIN) --
        if uncertain_mgs:
            els += sec_hdr("Needs Confirmation", GREY)
            els.append(Paragraph("The following items could not be conclusively matched. Manual review is recommended before finalising the order.", body)); els.append(Spacer(1,4))
            rows = [[Paragraph(h, th_s) for h in ["Item Code","Available In","Reason for Uncertainty"]]]
            for mg in uncertain_mgs:
                d, o, a = mg.design_item, mg.cabinet_list_item, mg.ack_item
                avail = (["Design Drawing"] if d else []) + (["Purchase Order"] if o else []) + (["Mfr. Confirmation"] if a else [])
                discs = mg_disc_map.get(mg.id, [])
                reason = (discs[0].explanation if discs and discs[0].explanation else "Automatic matching was inconclusive.")[:120]
                rows.append([Paragraph(f"<b>{_sku(mg)}</b>", small_b), Paragraph(", ".join(avail) or "-", small), Paragraph(reason, small)])
            t = Table(rows, colWidths=[80,160,300], repeatRows=1); t.setStyle(tbl_style(GREY,[WHITE,SLATE_50])); els.append(t)
            els.append(Spacer(1, 10))

        # -- 9. SPECIFICATION DIFFERENCES SUMMARY --
        spec_discs = [d for d in discrepancies if d.field and d.field != "item_presence"]
        if spec_discs:
            els += sec_hdr("Specification Differences Summary", ORANGE)
            els.append(Paragraph("A summary of key specification fields where differences were found.", body)); els.append(Spacer(1,4))
            fc: Dict[str, Any] = {}
            for d in spec_discs:
                f2 = d.field or "other"; sev = (d.severity.value if hasattr(d.severity,"value") else str(d.severity)).upper()
                if f2 not in fc: fc[f2] = {"count":0,"max_sev":"INFO"}
                fc[f2]["count"] += 1
                if {"CRITICAL":2,"WARNING":1,"INFO":0}.get(sev,0) > {"CRITICAL":2,"WARNING":1,"INFO":0}.get(fc[f2]["max_sev"],0): fc[f2]["max_sev"]=sev
            rows = [[Paragraph(h, th_s) for h in ["Specification Field","Differences Found","Highest Severity"]]]
            sev_labels = {"CRITICAL":"\u26a0 Action Required","WARNING":"\u25ce Needs Review","INFO":"\u2139 For Your Info"}
            for f2, info in sorted(fc.items(), key=lambda x: -x[1]["count"]):
                sc = RED if info["max_sev"]=="CRITICAL" else (ORANGE if info["max_sev"]=="WARNING" else GREY)
                rows.append([Paragraph(_fl(f2),small), Paragraph(str(info["count"]),small),
                             Paragraph(f"<font color='{sc.hexval()}'><b>{sev_labels.get(info['max_sev'],info['max_sev'])}</b></font>",small)])
            t = Table(rows, colWidths=[220,120,200], repeatRows=1); t.setStyle(tbl_style(ORANGE,[WHITE,ORANGE_BG])); els.append(t)
            els.append(Spacer(1, 10))

        # -- 10. DOCUMENT RELATIONSHIP NOTE --
        note = ("<b>Note on Document Relationship:</b> The Purchase Order and Manufacturer Confirmation in this project "
                "may be related documents. If the Purchase Order was prepared from the Manufacturer Acknowledgment, "
                "independent verification between these two documents may not be available. CrossCheckPro has verified "
                "all three documents against the Design Drawing.")
        note_tbl = Table([[Paragraph(note, _ps("note", fontName="Helvetica", fontSize=8, leading=11, textColor=SLATE_700))]], colWidths=[540])
        note_tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),SLATE_50),("BOX",(0,0),(-1,-1),1,SLATE_200),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8)]))
        els.append(note_tbl); els.append(Spacer(1, 10))

        # -- 11. WHAT SHOULD BE DONE NEXT? --
        els += sec_hdr("What Should Be Done Next?", BLUE_A)
        steps = []
        if len(active_mgs) > 0 and len(matched_mgs) == len(active_mgs):
            steps.append("All items have been verified. You may proceed to finalise the order.")
        else:
            if missing_mgs:  steps.append(f"Review {len(missing_mgs)} missing item(s) with your dealer and confirm whether they should be added to the order.")
            if extra_mgs:    steps.append(f"Verify {len(extra_mgs)} extra item(s) with your dealer \u2014 confirm these are intentional additions.")
            if changed_mgs:  steps.append("Review specification differences \u2014 confirm all colour, finish, and door style changes are intentional.")
            if uncertain_mgs: steps.append(f"Manually review {len(uncertain_mgs)} item(s) that could not be automatically matched.")
            steps.append("Once all items are confirmed, use CrossCheckPro's Human Review feature to finalise the project.")
        for i, step in enumerate(steps, 1):
            els.append(Paragraph(f"{i}. {step}", body)); els.append(Spacer(1, 3))
        els.append(Spacer(1, 10))

        # -- 12. DOCUMENTS REVIEWED --
        els += sec_hdr("Documents Reviewed", GREY)
        doc_rows = [[Paragraph(h, th_s) for h in ["Document Type","File Name","Status"]]]
        order_label = "Cabinet List" if (order_d and getattr(order_d, "document_type", None) == DocumentType.CABINET_LIST) else "Purchase Order"
        for lbl, dobj in [("Design Drawing", design_d), (order_label, order_d), ("Manufacturer Confirmation", ack_d)]:
            if dobj:
                fname = dobj.original_filename or "-"
                status = dobj.status.value if hasattr(dobj.status,"value") else str(dobj.status)
            else:
                fname, status = "Not uploaded", "Missing"
            doc_rows.append([Paragraph(lbl,small), Paragraph(fname,small), Paragraph(status,small)])
        doc_tbl = Table(doc_rows, colWidths=[160,240,140], repeatRows=1)
        doc_tbl.setStyle(tbl_style(GREY,[WHITE,SLATE_50])); els.append(doc_tbl)

        pdf_doc.build(els, canvasmaker=NumberedCanvas)
        return buffer.getvalue()

    def _get_actionable_discrepancies(self, project_id: uuid.UUID, organization_id: uuid.UUID):
        project = self.db.scalars(
            select(Project).where(Project.id == project_id, Project.organization_id == organization_id)
        ).first()
        if not project:
            raise ResourceNotFoundError(message="Project not found")

        severity_order = {"Critical": 0, "CRITICAL": 0, "Warning": 1, "WARNING": 1, "Info": 2, "INFO": 2}
        discrepancies = self.db.scalars(
            select(Discrepancy).where(
                Discrepancy.project_id == project_id,
                Discrepancy.organization_id == organization_id,
                Discrepancy.status.in_(["OPEN", "ESCALATED"]),
            )
        ).all()
        discrepancies = sorted(
            discrepancies,
            key=lambda d: (severity_order.get(d.severity.value if hasattr(d.severity, "value") else str(d.severity), 3), d.created_at),
        )
        return project, discrepancies

    def _actionable_row(self, d: "Discrepancy") -> Dict[str, str]:
        mg = d.match_group
        sku = (mg.final_sku if mg and mg.final_sku else None) or "-"
        ack_line = "-"
        if mg and mg.ack_item and mg.ack_item.source_metadata:
            ack_line = mg.ack_item.source_metadata.get("line_number") or "-"
        severity = d.severity.value if hasattr(d.severity, "value") else str(d.severity)
        return {
            "sku": sku,
            "field": d.field,
            "design": self._format_val((d.source_values or {}).get("design")),
            "order": self._format_val((d.source_values or {}).get("order")),
            "ack": self._format_val((d.source_values or {}).get("acknowledgement")),
            "ack_line": str(ack_line),
            "severity": severity,
            "action": d.explanation or "-",
        }

    def generate_shareable_summary_csv_data(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> str:
        project, discrepancies = self._get_actionable_discrepancies(project_id, organization_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([f"CrossCheckPro — Action Items for {project.name}"])
        writer.writerow(["SKU", "Field", "Design", "Order", "Acknowledgement", "Ack Line #", "Severity", "Action Needed"])
        for d in discrepancies:
            row = self._actionable_row(d)
            writer.writerow([row["sku"], row["field"], row["design"], row["order"], row["ack"], row["ack_line"], row["severity"], row["action"]])
        return output.getvalue()

    def generate_shareable_summary_pdf_bytes(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> bytes:
        project, discrepancies = self._get_actionable_discrepancies(project_id, organization_id)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        PRIMARY = colors.HexColor("#0F172A")
        MUTED_TEXT = colors.HexColor("#64748B")
        BORDER_COLOR = colors.HexColor("#E2E8F0")
        BG_LIGHT = colors.HexColor("#F8FAFC")
        RED_COLOR = colors.HexColor("#DC2626")
        AMBER_COLOR = colors.HexColor("#D97706")

        title_style = ParagraphStyle('Title', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=15, leading=19, textColor=PRIMARY, spaceAfter=6)
        subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=MUTED_TEXT, spaceAfter=10)
        th_style = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=7, leading=8, textColor=colors.white)
        cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontName='Helvetica', fontSize=7.5, leading=9, textColor=PRIMARY)

        elements = [
            Paragraph(f"Action Items — {project.name}", title_style),
            Paragraph(
                f"Customer: {project.customer_name or '-'} | Dealer: {project.dealer_name or '-'} | "
                f"{len(discrepancies)} item(s) need action | Generated {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')}",
                subtitle_style,
            ),
        ]

        if not discrepancies:
            elements.append(Paragraph("No open action items — everything has been reviewed.", cell_style))
        else:
            headers = [Paragraph(h, th_style) for h in ["SKU", "Field", "Design", "Order", "Ack", "Line #", "Severity", "Action Needed"]]
            rows = [headers]
            for d in discrepancies:
                r = self._actionable_row(d)
                sev_color = RED_COLOR if r["severity"].upper() == "CRITICAL" else (AMBER_COLOR if r["severity"].upper() == "WARNING" else MUTED_TEXT)
                rows.append([
                    Paragraph(r["sku"], cell_style),
                    Paragraph(r["field"], cell_style),
                    Paragraph(r["design"], cell_style),
                    Paragraph(r["order"], cell_style),
                    Paragraph(r["ack"], cell_style),
                    Paragraph(r["ack_line"], cell_style),
                    Paragraph(f'<font color="{sev_color.hexval()}" size="7"><b>{r["severity"].upper()}</b></font>', cell_style),
                    Paragraph(r["action"], cell_style),
                ])
            table = Table(rows, colWidths=[55, 45, 58, 58, 58, 30, 52, 184], repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
                ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ]))
            elements.append(table)

        doc.build(elements)
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
