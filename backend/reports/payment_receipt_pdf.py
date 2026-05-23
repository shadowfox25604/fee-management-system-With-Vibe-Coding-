"""School fee payment receipt PDF (ReportLab)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOGO_PATH = _PROJECT_ROOT / "frontend" / "assets" / "ace_school_logo.jpeg"
FALLBACK_LOGO_PATH = _PROJECT_ROOT / "frontend" / "assets" / "school_logo.png"

SCHOOL_DISPLAY_NAME = "ACE HIGH SCHOOL"

# Refined palette: deep slate header, warm accent, soft surfaces
_PRIMARY = colors.HexColor("#0f2744")
_ACCENT = colors.HexColor("#b8860b")
_SURFACE = colors.HexColor("#f4f6f9")
_CARD_EDGE = colors.HexColor("#c5cdd8")
_LINE = colors.HexColor("#dce1e8")
_TEXT = colors.HexColor("#1e2430")
_MUTED = colors.HexColor("#5a6573")


def _money(v: float) -> str:
    return f"{float(v):,.2f}"


def _p(text: str) -> str:
    return escape(str(text if text is not None else ""))


def render_payment_receipt(
    output_path: Path,
    *,
    student_name: str,
    roll_number: str,
    class_name: str,
    section: str,
    guardian_name: str,
    school_fees_paid: float,
    van_fees_paid: float,
    discount: float,
    receipt_no: str,
    generated_at: datetime,
    school_name: str = SCHOOL_DISPLAY_NAME,
    logo_path: Path | None = None,
) -> None:
    """``discount`` is kept for call-site parity with split payments; it is not itemized on the PDF."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logo = logo_path if logo_path is not None else DEFAULT_LOGO_PATH
    if not logo.exists() and logo_path is None and FALLBACK_LOGO_PATH.exists():
        logo = FALLBACK_LOGO_PATH
    styles = getSampleStyleSheet()

    school_title = ParagraphStyle(
        "SchoolTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=26,
        leading=30,
        textColor=_PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=10,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=_TEXT,
        alignment=TA_LEFT,
    )
    body_bold = ParagraphStyle(
        "BodyBold",
        parent=body,
        fontName="Helvetica-Bold",
    )
    meta_center = ParagraphStyle(
        "MetaCenter",
        parent=body,
        fontSize=9.5,
        textColor=_MUTED,
        alignment=TA_CENTER,
        spaceBefore=2,
        spaceAfter=2,
    )
    receipt_no_style = ParagraphStyle(
        "ReceiptNo",
        parent=body,
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=_PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    label_style = ParagraphStyle(
        "Lbl",
        parent=body,
        textColor=_MUTED,
        fontSize=9,
    )
    footer_style = ParagraphStyle(
        "Foot",
        parent=body,
        fontSize=9.5,
        textColor=_MUTED,
        alignment=TA_CENTER,
        spaceBefore=22,
        leading=13,
    )
    table_head = ParagraphStyle(
        "TblHead",
        parent=body,
        fontName="Helvetica-Bold",
        textColor=_PRIMARY,
        fontSize=10,
    )
    table_head_r = ParagraphStyle(
        "TblHeadR",
        parent=table_head,
        alignment=TA_RIGHT,
    )
    cell_r = ParagraphStyle(
        "CellR",
        parent=body,
        alignment=TA_RIGHT,
    )

    story: list = []
    usable_w = A4[0] - 3.6 * cm

    # --- Header: school name top centre, logo below (school asset) ---
    story.append(Paragraph(_p(school_name), school_title))

    logo_flow: Image | Spacer
    if logo.exists():
        try:
            logo_flow = Image(str(logo), width=3.2 * cm, height=3.2 * cm)
        except OSError:
            logo_flow = Spacer(1, 0.2 * cm)
    else:
        logo_flow = Spacer(1, 0.2 * cm)

    logo_wrap = Table([[logo_flow]], colWidths=[usable_w])
    logo_wrap.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(logo_wrap)

    accent_bar = Table([[""]], colWidths=[usable_w], rowHeights=[0.14 * cm])
    accent_bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _ACCENT)]))
    story.append(accent_bar)
    story.append(Spacer(1, 0.4 * cm))

    # --- Date/time of generation & receipt number (no payment date / mode) ---
    dt_line = generated_at.strftime("%B %d, %Y, %I:%M %p")
    story.append(Paragraph(_p(f"Generated: {dt_line}"), meta_center))
    story.append(Paragraph(f"Receipt No. <b>{_p(receipt_no)}</b>", receipt_no_style))

    # --- Student block ---
    info_rows = [
        [Paragraph("<b>Roll number</b>", label_style), Paragraph(_p(roll_number), body_bold)],
        [Paragraph("<b>Student name</b>", label_style), Paragraph(_p(student_name), body_bold)],
        [Paragraph("<b>Class</b>", label_style), Paragraph(_p(class_name), body)],
        [Paragraph("<b>Section</b>", label_style), Paragraph(_p(section), body)],
        [Paragraph("<b>Guardian name</b>", label_style), Paragraph(_p(guardian_name), body)],
    ]
    info_tbl = Table(info_rows, colWidths=[3.4 * cm, usable_w - 3.4 * cm - 24])
    info_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, _CARD_EDGE),
                ("LINEBELOW", (0, 0), (-1, -2), 0.35, _LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(info_tbl)
    story.append(Spacer(1, 0.55 * cm))

    # --- Fee table (print only): amount paid = school + van ---
    amount_paid = float(school_fees_paid or 0.0) + float(van_fees_paid or 0.0)

    fee_data = [
        [
            Paragraph("Description", table_head),
            Paragraph("Amount (INR)", table_head_r),
        ],
        [
            Paragraph("Amount paid", body),
            Paragraph(_money(amount_paid), cell_r),
        ],
    ]
    fee_tbl = Table(fee_data, colWidths=[usable_w * 0.64, usable_w * 0.36])
    fee_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _SURFACE),
                ("TEXTCOLOR", (0, 0), (-1, 0), _PRIMARY),
                ("LINEBELOW", (0, 0), (-1, 0), 1, _PRIMARY),
                ("LINEBELOW", (0, -1), (-1, -1), 1.5, _ACCENT),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(fee_tbl)

    story.append(
        Paragraph(
            "Thank you for the payment. For any further inquiries, please contact the school management.",
            footer_style,
        )
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
        title="Fee receipt",
    )
    doc.build(story)
